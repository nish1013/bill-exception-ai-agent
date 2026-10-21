from uuid import UUID

from celery import Task, shared_task
from celery.exceptions import Reject

from payables.adapters.broker.routes import PURCHASE_ORDER_ADDED_TASK
from payables.adapters.orm.check_job_repository import CheckJobOrmRepository
from payables.adapters.orm.exception_repository import ExceptionOrmRepository
from payables.adapters.orm.outbox_repository import OutboxOrmRepository
from payables.adapters.orm.tenancy import tenant_transaction
from payables.application.recheck_po_mismatches import recheck_po_mismatches
from payables.domain.purchase_orders import PurchaseOrderAdded

MAX_ATTEMPTS = 3


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
