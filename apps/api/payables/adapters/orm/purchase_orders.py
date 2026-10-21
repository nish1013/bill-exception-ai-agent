import uuid
from uuid import UUID

from django.db import IntegrityError, models, transaction

from payables.adapters.orm.constraints import money_constraints, violated_constraint
from payables.adapters.orm.suppliers import SupplierRow
from payables.adapters.orm.tenants import Tenant
from payables.domain.errors import ConflictError
from payables.domain.money import Money
from payables.domain.purchase_orders import PurchaseOrder
from payables.domain.text import DocumentNumber

PO_NUMBER_KEY = "purchase_order_tenant_number_key"


class PurchaseOrderRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    # The migration adds the key (tenant_id, supplier_id), so both rows share a tenant (I1).
    supplier = models.ForeignKey(
        SupplierRow, on_delete=models.PROTECT, db_constraint=False, related_name="+"
    )
    po_number = models.TextField()
    po_number_norm = models.TextField()
    amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "purchase_order"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "po_number_norm"], name=PO_NUMBER_KEY),
            *money_constraints("purchase_order", "amount_minor"),
        ]


class PurchaseOrderOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def add(self, supplier_id: UUID, po_number: DocumentNumber, amount: Money) -> PurchaseOrder:
        try:
            with transaction.atomic():
                row = PurchaseOrderRow.objects.create(
                    tenant_id=self._tenant_id,
                    supplier_id=supplier_id,
                    po_number=po_number.raw,
                    po_number_norm=po_number.normalised,
                    amount_minor=amount.minor_units,
                    currency=amount.currency,
                )
        except IntegrityError as error:
            if violated_constraint(error) == PO_NUMBER_KEY:
                raise ConflictError(f"PO {po_number.normalised} exists") from error
            raise
        return _purchase_order(row)

    def find(self, po_number: str) -> PurchaseOrder | None:
        row = PurchaseOrderRow.objects.filter(
            tenant_id=self._tenant_id, po_number_norm=po_number
        ).first()
        return None if row is None else _purchase_order(row)


def _purchase_order(row: PurchaseOrderRow) -> PurchaseOrder:
    return PurchaseOrder(
        id=row.id,
        supplier_id=row.supplier_id,
        po_number=row.po_number,
        amount=Money(row.amount_minor, row.currency),
    )
