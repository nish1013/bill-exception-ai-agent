from typing import Protocol
from uuid import UUID

from payables.domain.money import Money
from payables.domain.purchase_orders import PurchaseOrder
from payables.domain.text import DocumentNumber


class PurchaseOrderRepository(Protocol):
    def add(self, supplier_id: UUID, po_number: DocumentNumber, amount: Money) -> PurchaseOrder: ...

    def find(self, po_number: str) -> PurchaseOrder | None: ...
