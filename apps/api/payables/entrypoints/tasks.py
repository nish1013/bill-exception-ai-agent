import time
from uuid import UUID

from celery import Task, current_app, shared_task
from celery.exceptions import Reject
from django.conf import settings

from payables.adapters.accounting import accounting_from_settings, send_stub_callback
from payables.adapters.broker import (
    APPLY_FIX_PROPOSAL_TASK,
    CHECK_BILL_TASK,
    DRAFT_FIX_PROPOSAL_TASK,
    PURCHASE_ORDER_ADDED_TASK,
    STUB_CALLBACK_TASK,
)
from payables.adapters.channels import ChannelsConsoleEvents
from payables.adapters.llm import llm_from_settings
from payables.adapters.orm.audit import AuditOrmLog
from payables.adapters.orm.checks import CheckedBillOrmRepository, CheckJobOrmRepository
from payables.adapters.orm.exceptions import ExceptionOrmRepository, ResolutionOrmRepository
from payables.adapters.orm.outbox import OutboxOrmRepository
from payables.adapters.orm.proposals import ProposalOrmRepository, ProposalSyncOrmRepository
from payables.adapters.orm.purchase_orders import PurchaseOrderOrmRepository
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.checks import (
    check_bill,
    publish_check_progress,
    recheck_po_mismatches,
    record_check_result,
)
from payables.application.proposals import (
    draft_scope,
    fail_draft,
    finish_draft,
    publish_proposal_ready,
    run_agent,
)
from payables.application.sync import (
    fail_apply,
    finish_apply,
    publish_sync_changed,
    send_actions,
    start_apply,
)
from payables.domain.checks.jobs import CheckBill, CheckJob, CheckResult
from payables.domain.proposals.proposals import (
    ApplyFixProposal,
    DraftFixProposal,
    FixProposalReady,
)
from payables.domain.proposals.sync import (
    MAX_APPLY_ATTEMPTS,
    ProposalSyncChanged,
    is_last_attempt,
    retry_delay_seconds,
)
from payables.domain.purchase_orders import PurchaseOrderAdded

MAX_ATTEMPTS = 3


@shared_task(
    bind=True,
    name=CHECK_BILL_TASK,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=MAX_ATTEMPTS - 1,
    soft_time_limit=30,
    time_limit=40,
)
def check_bill_task(self: Task, tenant_id: str, job_id: str, bill_id: str) -> None:
    command = CheckBill(UUID(tenant_id), UUID(job_id), UUID(bill_id))
    jobs = CheckJobOrmRepository(command.tenant_id)
    try:
        with tenant_transaction(command.tenant_id, settings.CHECK_LOCK_TIMEOUT_MS):
            job = check_bill(
                command,
                CheckedBillOrmRepository(command.tenant_id),
                PurchaseOrderOrmRepository(command.tenant_id),
                ExceptionOrmRepository(command.tenant_id),
                ResolutionOrmRepository(command.tenant_id),
                jobs,
            )
    except Exception as error:
        if self.request.retries < MAX_ATTEMPTS - 1:
            raise self.retry(exc=error, countdown=2**self.request.retries) from error
        # The third failure: the bill is failed in its job, and the message goes to the DLQ (D17).
        with tenant_transaction(command.tenant_id):
            job = record_check_result(command, CheckResult.FAILED, type(error).__name__, jobs)
        _publish_progress(command, job)
        raise Reject(error, requeue=False) from error
    _publish_progress(command, job)


@shared_task(
    bind=True,
    name=PURCHASE_ORDER_ADDED_TASK,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=MAX_ATTEMPTS - 1,
    soft_time_limit=30,
    time_limit=40,
)
def purchase_order_added_task(self: Task, event_id: str, tenant_id: str, po_number: str) -> None:
    event = PurchaseOrderAdded(UUID(event_id), UUID(tenant_id), po_number)
    try:
        with tenant_transaction(event.tenant_id):
            recheck_po_mismatches(
                event,
                ExceptionOrmRepository(event.tenant_id),
                CheckJobOrmRepository(event.tenant_id),
                OutboxOrmRepository(event.tenant_id),
            )
    except Exception as error:
        if self.request.retries < MAX_ATTEMPTS - 1:
            raise self.retry(exc=error, countdown=2**self.request.retries) from error
        # The third failure goes to the DLQ, where the owner can replay it (D17, D43).
        raise Reject(error, requeue=False) from error


@shared_task(
    bind=True,
    name=DRAFT_FIX_PROPOSAL_TASK,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=MAX_ATTEMPTS - 1,
    soft_time_limit=75,
    time_limit=90,
)
def draft_fix_proposal_task(self: Task, tenant_id: str, proposal_id: str) -> None:
    command = DraftFixProposal(UUID(tenant_id), UUID(proposal_id))
    proposals = ProposalOrmRepository(command.tenant_id)
    audit = AuditOrmLog(command.tenant_id)
    try:
        with tenant_transaction(command.tenant_id):
            scope = draft_scope(command, proposals)
        if scope is None:
            return
        # No transaction stays open while the model runs (max 60 s, D20).
        outcome = run_agent(scope, llm_from_settings(), time.monotonic)
        with tenant_transaction(command.tenant_id):
            ready = finish_draft(command, outcome, proposals, audit)
    except Exception as error:
        if self.request.retries < MAX_ATTEMPTS - 1:
            raise self.retry(exc=error, countdown=2**self.request.retries) from error
        with tenant_transaction(command.tenant_id):
            ready = fail_draft(command, proposals, audit)
        _publish_ready(command, ready)
        raise Reject(error, requeue=False) from error
    _publish_ready(command, ready)


@shared_task(
    bind=True,
    name=APPLY_FIX_PROPOSAL_TASK,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=MAX_APPLY_ATTEMPTS - 1,
    soft_time_limit=30,
    time_limit=40,
)
def apply_fix_proposal_task(self: Task, tenant_id: str, proposal_id: str) -> None:
    command = ApplyFixProposal(UUID(tenant_id), UUID(proposal_id))
    proposals = ProposalSyncOrmRepository(command.tenant_id)
    retries = self.request.retries
    try:
        with tenant_transaction(command.tenant_id):
            started = start_apply(command, proposals)
        if started is None:
            return
        _publish_sync(command, started.changed)
        # No transaction stays open while accounting answers.
        results = send_actions(started.actions, accounting_from_settings(current_app))
        with tenant_transaction(command.tenant_id):
            outcome = finish_apply(command, results, is_last_attempt(retries), proposals)
    except Exception as error:
        if not is_last_attempt(retries):
            raise _retry_apply(self, retries, error) from error
        with tenant_transaction(command.tenant_id):
            changed = fail_apply(command, proposals)
        _publish_sync(command, changed)
        raise Reject(error, requeue=False) from error
    _publish_sync(command, outcome.changed)
    if outcome.retry:
        raise _retry_apply(self, retries, None)


@shared_task(
    bind=True,
    name=STUB_CALLBACK_TASK,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=MAX_ATTEMPTS - 1,
    soft_time_limit=10,
    time_limit=20,
)
def stub_accounting_callback_task(self: Task, sync_key: str) -> None:
    # The demo accounting stub confirms an accepted action by a signed callback (D51, US16).
    try:
        send_stub_callback(UUID(sync_key))
    except Exception as error:
        if self.request.retries < MAX_ATTEMPTS - 1:
            raise self.retry(exc=error, countdown=2**self.request.retries) from error
        raise Reject(error, requeue=False) from error


def _retry_apply(task: Task, retries: int, error: Exception | None):
    delay = retry_delay_seconds(retries, settings.APPLY_FIRST_RETRY_SECONDS)
    return task.retry(exc=error, countdown=delay)


def _publish_sync(command: ApplyFixProposal, changed: ProposalSyncChanged | None) -> None:
    publish_sync_changed(command.tenant_id, changed, ChannelsConsoleEvents())


def _publish_ready(command: DraftFixProposal, ready: FixProposalReady | None) -> None:
    if ready is not None:
        publish_proposal_ready(command.tenant_id, ready, ChannelsConsoleEvents())


def _publish_progress(command: CheckBill, job: CheckJob | None) -> None:
    # After the commit: an event never shows a result that a rollback removed.
    if job is not None:
        publish_check_progress(command.tenant_id, job, ChannelsConsoleEvents())
