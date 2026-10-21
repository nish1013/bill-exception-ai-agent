from django.db import connections

from payables.adapters.orm.check_job_repository import CheckJobOrmRepository
from payables.adapters.orm.outbox_repository import OutboxOrmRepository
from payables.adapters.orm.tenancy import tenant_transaction
from payables.application.checks import requeue_stale_check_job
from payables.entrypoints.relay.sweeper import sweep_stale_check_jobs
from tests.check_data import add_bill, check, start_job
from tests.concurrency import owner_count
from tests.tenants import T1


def _queued_for(job_id, seconds: int) -> None:
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            "UPDATE check_job SET enqueued_at = now() - make_interval(secs => %s) WHERE id = %s",
            [seconds, job_id],
        )
        cursor.execute("UPDATE outbox SET sent_at = now()")


def _unsent(job_id) -> int:
    return owner_count("outbox", "sent_at IS NULL AND payload->>'job_id' = %s", [str(job_id)])


def test_us5_queued_5_min_enqueued_again(committed_db):
    b1, b2 = add_bill("K1"), add_bill("K2", invoice_number="INV-002")
    j1 = start_job([b1, b2])
    _queued_for(j1.id, 301)

    assert sweep_stale_check_jobs() == 2

    assert _unsent(j1.id) == 2
    assert sweep_stale_check_jobs() == 0


def test_us5_queued_under_5_min_left_alone(committed_db):
    j1 = start_job([add_bill("K1")])
    _queued_for(j1.id, 299)

    assert sweep_stale_check_jobs() == 0
    assert _unsent(j1.id) == 0


def test_us5_running_job_left_alone(committed_db):
    b1, b2 = add_bill("K1"), add_bill("K2", invoice_number="INV-002")
    j1 = start_job([b1, b2])
    check(j1.id, b1)
    _queued_for(j1.id, 600)

    assert sweep_stale_check_jobs() == 0


def test_us5_job_requeued_by_another_sweep_left_alone(committed_db):
    j1 = start_job([add_bill("K1")])
    _queued_for(j1.id, 301)
    assert sweep_stale_check_jobs() == 1

    with tenant_transaction(T1):
        again = requeue_stale_check_job(
            T1, j1.id, CheckJobOrmRepository(T1), OutboxOrmRepository(T1)
        )

    assert again == 0
