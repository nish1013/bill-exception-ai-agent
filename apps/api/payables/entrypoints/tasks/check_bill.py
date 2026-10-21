from uuid import UUID

from celery import Task, shared_task
from celery.exceptions import Reject
from django.conf import settings

from payables.adapters.broker.routes import CHECK_BILL_TASK
from payables.adapters.orm.check_job_repository import CheckJobOrmRepository
from payables.adapters.orm.checked_bill_repository import CheckedBillOrmRepository
from payables.adapters.orm.exception_repository import ExceptionOrmRepository
from payables.adapters.orm.tenancy import tenant_transaction
from payables.application.check_bill import check_bill, record_check_result
from payables.domain.checks.check_bill_command import CheckBill
from payables.domain.checks.check_result import CheckResult

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
            check_bill(
                command,
                CheckedBillOrmRepository(command.tenant_id),
                ExceptionOrmRepository(command.tenant_id),
                jobs,
            )
    except Exception as error:
        if self.request.retries < MAX_ATTEMPTS - 1:
            raise self.retry(exc=error, countdown=2**self.request.retries) from error
        # The third failure: the bill is failed in its job, and the message goes to the DLQ (D17).
        with tenant_transaction(command.tenant_id):
            record_check_result(command, CheckResult.FAILED, type(error).__name__, jobs)
        raise Reject(error, requeue=False) from error
