import uuid
from uuid import UUID

from django.db import IntegrityError, models, transaction

from payables.adapters.orm.constraints import money_constraints, violated_constraint
from payables.adapters.orm.suppliers import SupplierRow
from payables.adapters.orm.tenants import Tenant
from payables.application.bills import BillListItem
from payables.application.pages import ListPage
from payables.domain.bills import BillDraft, IdempotencyKey, StoredBill

IDEMPOTENCY_KEY = "bill_tenant_idempotency_key"
STORED_FIELDS = ("id", "supplier_id", "payload_hash")
LIST_LIMIT = 500


class BillRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    # The migration adds the key (tenant_id, supplier_id), so both rows share a tenant (I1).
    supplier = models.ForeignKey(
        SupplierRow, on_delete=models.PROTECT, db_constraint=False, related_name="+"
    )
    invoice_number = models.TextField()
    invoice_number_norm = models.TextField()
    amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    vat_amount_minor = models.BigIntegerField(null=True)
    issue_date = models.DateField()
    po_number = models.TextField(null=True)
    po_number_norm = models.TextField(null=True)
    has_receipt = models.BooleanField()
    idempotency_key = models.CharField(max_length=255)
    payload_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "bill"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "idempotency_key"], name=IDEMPOTENCY_KEY),
            models.UniqueConstraint(fields=["tenant", "id"], name="bill_tenant_id_key"),
            *money_constraints("bill", "amount_minor", "vat_amount_minor"),
        ]
        indexes = [
            models.Index(
                fields=["supplier", "invoice_number_norm"], name="bill_supplier_number_idx"
            ),
            models.Index(fields=["supplier", "amount_minor"], name="bill_supplier_amount_idx"),
        ]


class BillOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def find_by_key(self, key: IdempotencyKey) -> StoredBill | None:
        row = (
            BillRow.objects.filter(tenant_id=self._tenant_id, idempotency_key=key.value)
            .order_by("created_at")
            .values(*STORED_FIELDS)
            .first()
        )
        return None if row is None else StoredBill(**row)

    def find(self, bill_id: UUID) -> StoredBill | None:
        row = BillRow.objects.filter(tenant_id=self._tenant_id, id=bill_id).values(*STORED_FIELDS)
        found = row.first()
        return None if found is None else StoredBill(**found)

    def add_or_find(
        self, supplier_id: UUID, key: IdempotencyKey, payload_hash: str, draft: BillDraft
    ) -> StoredBill:
        try:
            with transaction.atomic():
                row = BillRow.objects.create(
                    tenant_id=self._tenant_id,
                    supplier_id=supplier_id,
                    invoice_number=draft.invoice_number.raw,
                    invoice_number_norm=draft.invoice_number.normalised,
                    amount_minor=draft.amount.minor_units,
                    currency=draft.amount.currency,
                    vat_amount_minor=draft.vat_amount.minor_units if draft.vat_amount else None,
                    issue_date=draft.issue_date,
                    po_number=draft.po_number.raw if draft.po_number else None,
                    po_number_norm=draft.po_number.normalised if draft.po_number else None,
                    has_receipt=draft.has_receipt,
                    idempotency_key=key.value,
                    payload_hash=payload_hash,
                )
        except IntegrityError as error:
            # A concurrent ingest with the same key committed first (I4).
            found = self.find_by_key(key) if violated_constraint(error) == IDEMPOTENCY_KEY else None
            if found is None:
                raise
            return found
        return StoredBill(id=row.id, supplier_id=supplier_id, payload_hash=payload_hash)


class BillListOrmQuery:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def latest(self) -> ListPage[BillListItem]:
        bills = BillRow.objects.filter(tenant_id=self._tenant_id)
        rows = bills.order_by("-created_at", "-id").values(
            "id",
            "supplier__name",
            "invoice_number",
            "amount_minor",
            "currency",
            "issue_date",
            "has_receipt",
            "created_at",
        )[:LIST_LIMIT]
        items = [
            BillListItem(
                id=row["id"],
                supplier_name=row["supplier__name"],
                invoice_number=row["invoice_number"],
                amount=row["amount_minor"],
                currency=row["currency"],
                issue_date=row["issue_date"],
                has_receipt=row["has_receipt"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
        return ListPage(items=items, total_count=bills.count())
