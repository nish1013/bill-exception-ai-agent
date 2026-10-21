from payables.adapters.orm.check_job_repository import CheckJobOrmRepository
from payables.adapters.orm.outbox_repository import OutboxOrmRepository
from payables.adapters.orm.stale_check_jobs import stale_check_jobs
from payables.adapters.orm.tenancy import tenant_transaction
from payables.application.requeue_stale_check_job import requeue_stale_check_job
from payables.domain.checks.check_job import QUEUED_STALE_AFTER


def sweep_stale_check_jobs() -> int:
    requeued = 0
    for tenant_id, job_id in stale_check_jobs(QUEUED_STALE_AFTER):
        with tenant_transaction(tenant_id):
            requeued += requeue_stale_check_job(
                tenant_id,
                job_id,
                CheckJobOrmRepository(tenant_id),
                OutboxOrmRepository(tenant_id),
            )
    return requeued
