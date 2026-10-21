from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StoredBill:
    id: UUID
    supplier_id: UUID
    payload_hash: str
