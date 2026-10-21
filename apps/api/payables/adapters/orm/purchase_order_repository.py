from uuid import UUID

from django.db import IntegrityError, transaction

from payables.adapters.orm.integrity import violated_constraint
from payables.adapters.orm.purchase_order import PO_NUMBER_KEY, PurchaseOrderRow
from payables.domain.document_number import DocumentNumber
from payables.domain.errors import ConflictError
from payables.domain.money import Money
from payables.domain.purchase_order import PurchaseOrder


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
        return PurchaseOrder(
            id=row.id, supplier_id=supplier_id, po_number=row.po_number, amount=amount
        )
