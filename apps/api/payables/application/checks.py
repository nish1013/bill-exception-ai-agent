from collections.abc import Iterable
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from payables.application.authorization import require_role
from payables.application.console_events import ConsoleEvents
from payables.application.exceptions import ExceptionRepository, ResolutionRepository
from payables.application.outbox import Outbox
from payables.application.purchase_orders import PurchaseOrderRepository
from payables.domain.access import SYSTEM_ACTOR, Principal, Role
from payables.domain.checks.exceptions import changes_after_check
from payables.domain.checks.jobs import (
    QUEUED_STALE_AFTER,
    CheckBill,
    CheckJob,
    CheckResult,
    recheck_jobs,
)
from payables.domain.checks.rules import CheckedBill, Rule, run_rules
from payables.domain.errors import NotFoundError
from payables.domain.purchase_orders import PurchaseOrder, PurchaseOrderAdded


class CheckJobRepository(Protocol):
    def add(
        self, requested_by: str, bill_ids: list[UUID], job_id: UUID | None = None
    ) -> CheckJob: ...

    def find(self, job_id: UUID) -> CheckJob | None: ...

    def is_pending(self, job_id: UUID, bill_id: UUID) -> bool: ...

    def lock(self, job_id: UUID) -> CheckJob | None: ...

    def save_result(
        self, job: CheckJob, bill_id: UUID, result: CheckResult, error: str | None
    ) -> None: ...

    def requeue_if_stale(self, job_id: UUID, stale_after: timedelta) -> list[UUID]: ...


class CheckedBillRepository(Protocol):
    def existing_ids(self, bill_ids: list[UUID]) -> set[UUID]: ...

    def get(self, bill_id: UUID) -> CheckedBill: ...

    def earlier_alike(self, bill: CheckedBill) -> list[CheckedBill]: ...


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


def get_check_job(job_id: UUID, jobs: CheckJobRepository) -> CheckJob:
    job = jobs.find(job_id)
    if job is None:
        raise NotFoundError("check job not found")
    return job


def check_bill(
    command: CheckBill,
    bills: CheckedBillRepository,
    purchase_orders: PurchaseOrderRepository,
    exceptions: ExceptionRepository,
    resolutions: ResolutionRepository,
    jobs: CheckJobRepository,
) -> CheckJob | None:
    if not jobs.is_pending(command.job_id, command.bill_id):
        return None
    bill = bills.get(command.bill_id)
    findings = run_rules(bill, bills.earlier_alike(bill), _purchase_order(bill, purchase_orders))
    exceptions.add_missing(bill.id, findings)
    changes = changes_after_check(findings, exceptions.on_bill(bill.id))
    resolutions.resolve_by_system(changes.to_resolve)
    resolutions.reopen(changes.to_reopen)
    return record_check_result(command, CheckResult.OK, None, jobs)


def record_check_result(
    command: CheckBill, result: CheckResult, error: str | None, jobs: CheckJobRepository
) -> CheckJob | None:
    job = jobs.lock(command.job_id)
    # A repeat delivery finds the result already written (D42).
    if job is None or not jobs.is_pending(command.job_id, command.bill_id):
        return None
    job.record(result)
    jobs.save_result(job, command.bill_id, result, error)
    return job


def publish_check_progress(tenant_id: UUID, job: CheckJob, events: ConsoleEvents) -> None:
    for event in job.progress_events():
        events.publish(tenant_id, event)


def requeue_stale_check_job(
    tenant_id: UUID, job_id: UUID, jobs: CheckJobRepository, outbox: Outbox
) -> int:
    bill_ids = jobs.requeue_if_stale(job_id, QUEUED_STALE_AFTER)
    outbox.add([CheckBill(tenant_id, job_id, bill_id) for bill_id in bill_ids])
    return len(bill_ids)


def recheck_po_mismatches(
    event: PurchaseOrderAdded,
    exceptions: ExceptionRepository,
    jobs: CheckJobRepository,
    outbox: Outbox,
) -> int:
    bill_ids = exceptions.bills_with_open(Rule.PO_MISMATCH, event.po_number)
    planned = recheck_jobs(event.event_id, bill_ids)
    if not planned or jobs.find(planned[0].id) is not None:
        return 0
    for job in planned:
        jobs.add(SYSTEM_ACTOR, job.bill_ids, job.id)
        outbox.add([CheckBill(event.tenant_id, job.id, bill_id) for bill_id in job.bill_ids])
    return len(bill_ids)


def _purchase_order(
    bill: CheckedBill, purchase_orders: PurchaseOrderRepository
) -> PurchaseOrder | None:
    return None if bill.po_number is None else purchase_orders.find(bill.po_number)
