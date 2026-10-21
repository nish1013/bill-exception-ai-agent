from typing import Protocol
from uuid import UUID

from payables.domain.document_number import DocumentNumber
from payables.domain.money import Money
from payables.domain.purchase_order import PurchaseOrder


class PurchaseOrderRepository(Protocol):
    def add(self, supplier_id: UUID, po_number: DocumentNumber, amount: Money) -> PurchaseOrder: ...

    def find(self, po_number: str) -> PurchaseOrder | None: ...
