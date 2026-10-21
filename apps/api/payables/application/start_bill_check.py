from collections.abc import Iterable
from uuid import UUID

from payables.application.authorization import require_role
from payables.application.ports.check_job_repository import CheckJobRepository
from payables.application.ports.checked_bill_repository import CheckedBillRepository
from payables.application.ports.outbox import Outbox
from payables.domain.access import Principal, Role
from payables.domain.checks.jobs import CheckBill, CheckJob
from payables.domain.errors import NotFoundError


def start_bill_check(
    principal: Principal,
    bill_ids: Iterable[UUID],
    bills: CheckedBillRepository,
    jobs: CheckJobRepository,
    outbox: Outbox,
) -> CheckJob:
    require_role(principal, Role.CLERK)
    to_check = CheckJob.bills_to_check(bill_ids)
    if bills.existing_ids(to_check) != set(to_check):
        raise NotFoundError("bill not found")
    job = jobs.add(principal.subject, to_check)
    # The job and its messages commit in the caller's transaction (I14, D4).
    outbox.add([CheckBill(principal.tenant_id, job.id, bill_id) for bill_id in to_check])
    return job
