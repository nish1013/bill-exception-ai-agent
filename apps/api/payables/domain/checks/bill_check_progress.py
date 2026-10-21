from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class BillCheckProgress:
    job_id: UUID
    seq: int
    percent: int
