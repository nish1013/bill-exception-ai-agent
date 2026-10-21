from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PurchaseOrderAdded:
    event_id: UUID
    tenant_id: UUID
    po_number: str
