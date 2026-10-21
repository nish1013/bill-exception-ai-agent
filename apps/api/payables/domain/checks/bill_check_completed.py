from dataclasses import dataclass
from uuid import UUID

from payables.domain.checks.check_job_status import CheckJobStatus


@dataclass(frozen=True)
class BillCheckCompleted:
    job_id: UUID
    seq: int
    status: CheckJobStatus
    failed_count: int
