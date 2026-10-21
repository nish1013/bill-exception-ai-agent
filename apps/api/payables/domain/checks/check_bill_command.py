from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CheckBill:
    tenant_id: UUID
    job_id: UUID
    bill_id: UUID
