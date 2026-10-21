from uuid import UUID

from django.db import IntegrityError, transaction

from payables.adapters.orm.bill import IDEMPOTENCY_KEY, BillRow
from payables.adapters.orm.integrity import violated_constraint
from payables.domain.bill_draft import BillDraft
from payables.domain.idempotency_key import IdempotencyKey
from payables.domain.stored_bill import StoredBill

STORED_FIELDS = ("id", "supplier_id", "payload_hash")


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
