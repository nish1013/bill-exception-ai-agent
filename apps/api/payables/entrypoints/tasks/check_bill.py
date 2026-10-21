from uuid import UUID

from celery import Task, shared_task
from celery.exceptions import Reject
from django.conf import settings

from payables.adapters.broker import CHECK_BILL_TASK
from payables.adapters.channels import ChannelsConsoleEvents
from payables.adapters.orm.checks import CheckedBillOrmRepository, CheckJobOrmRepository
from payables.adapters.orm.exceptions import ExceptionOrmRepository, ResolutionOrmRepository
from payables.adapters.orm.purchase_orders import PurchaseOrderOrmRepository
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.checks import check_bill, publish_check_progress, record_check_result
from payables.domain.checks.jobs import CheckBill, CheckJob, CheckResult

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


def _publish_progress(command: CheckBill, job: CheckJob | None) -> None:
    # After the commit: an event never shows a result that a rollback removed.
    if job is not None:
        publish_check_progress(command.tenant_id, job, ChannelsConsoleEvents())
