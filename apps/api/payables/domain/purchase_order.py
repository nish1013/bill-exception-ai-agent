from dataclasses import dataclass
from uuid import UUID

from payables.domain.money import Money


@dataclass(frozen=True)
class PurchaseOrder:
    id: UUID
    supplier_id: UUID
    po_number: str
    amount: Money
