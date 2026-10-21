from uuid import UUID

from payables.application.ports.check_job_repository import CheckJobRepository
from payables.application.ports.outbox import Outbox
from payables.domain.checks.check_bill_command import CheckBill
from payables.domain.checks.check_job import QUEUED_STALE_AFTER


def requeue_stale_check_job(
    tenant_id: UUID, job_id: UUID, jobs: CheckJobRepository, outbox: Outbox
) -> int:
    bill_ids = jobs.requeue_if_stale(job_id, QUEUED_STALE_AFTER)
    outbox.add([CheckBill(tenant_id, job_id, bill_id) for bill_id in bill_ids])
    return len(bill_ids)
