from dataclasses import dataclass
from uuid import UUID

from payables.domain.money import Money
from payables.domain.text import DocumentNumber, is_blank


@dataclass(frozen=True)
class PurchaseOrder:
    id: UUID
    supplier_id: UUID
    po_number: str
    amount: Money


@dataclass(frozen=True)
class PurchaseOrderAdded:
    event_id: UUID
    tenant_id: UUID
    po_number: str


def po_number(raw: str) -> DocumentNumber:
    return DocumentNumber.parse(raw, "PO number")


def optional_po_number(raw: str | None) -> DocumentNumber | None:
    return None if is_blank(raw) else po_number(raw)
