from payables.adapters.orm.checks import CheckJobOrmRepository, stale_check_jobs
from payables.adapters.orm.outbox import OutboxOrmRepository
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.checks import requeue_stale_check_job
from payables.domain.checks.jobs import QUEUED_STALE_AFTER


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
