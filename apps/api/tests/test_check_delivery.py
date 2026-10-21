import os
import signal

import pytest
from django.db import connections, transaction

from config.celery import app
from payables.adapters.broker.celery_publisher import CeleryPublisher
from payables.adapters.broker.queues import CHECKS, dead_letter_name
from payables.adapters.outbox.relay import OutboxRelay
from tests.broker import (
    RELAY_COMMAND,
    dead_letter_retries,
    lock_waiters,
    process_env,
    queue_stats,
    running,
    wait_until,
    worker_command,
)
from tests.check_data import (
    add_bill,
    exceptions_on,
    job_row,
    start_job,
)
from tests.concurrency import owner_count
from tests.tenants import T1

pytestmark = pytest.mark.usefixtures("po_100")

HOLD_EXCEPTION_KEY = """
INSERT INTO exception (id, tenant_id, bill_id, rule, fingerprint, related_bill_id, created_at)
VALUES (gen_random_uuid(), %s, %s, 'duplicate', %s, %s, now())
"""


def _publish() -> int:
    return OutboxRelay(CeleryPublisher(app)).publish_pending()


def _consumed(broker_url: str) -> bool:
    return queue_stats(broker_url, CHECKS).consumers > 0


def _done(job_id) -> bool:
    return job_row(job_id)[0] in ("completed", "failed")


def _database() -> str:
    return connections["owner"].settings_dict["NAME"]


def test_us6_worker_checks_b2_from_the_checks_queue(committed_db, queues):
    b1 = add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    j1 = start_job([b1, b2])

    assert _publish() == 2
    with running(worker_command(CHECKS), process_env(queues)):
        wait_until(lambda: _done(j1.id), "J1 is done")

    assert job_row(j1.id) == ("completed", 0)
    assert exceptions_on(b2) == [("duplicate", b1)]


def test_d4_relay_restart_publishes_unsent_row(committed_db, queues):
    env = process_env(queues)
    with running(RELAY_COMMAND, env) as relay:
        os.killpg(relay.pid, signal.SIGKILL)
        relay.wait(10)

    j1 = start_job([add_bill("K1")])
    assert owner_count("outbox", "sent_at IS NULL") == 1

    with running(RELAY_COMMAND, env):
        wait_until(lambda: owner_count("outbox", "sent_at IS NULL") == 0, "the relay sent J1")

    assert queue_stats(queues, CHECKS).ready == 1
    assert job_row(j1.id)[0] == "queued"


def test_d43_killed_worker_check_bill_delivered_again(committed_db, queues):
    b1 = add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    j1 = start_job([b2])
    _publish()
    env = process_env(queues, CHECK_LOCK_TIMEOUT_MS="60000")

    with transaction.atomic(using="owner"), connections["owner"].cursor() as cursor:
        # The worker blocks on the job lock in its last step, then dies there.
        cursor.execute("SELECT 1 FROM check_job WHERE id = %s FOR UPDATE", [j1.id])
        with running(worker_command(CHECKS), env) as worker:
            wait_until(lambda: lock_waiters(_database()) == 1, "the worker waits on J1")
            os.killpg(worker.pid, signal.SIGKILL)
            worker.wait(10)
        wait_until(lambda: queue_stats(queues, CHECKS).ready == 1, "CheckBill is back")

    assert job_row(j1.id) == ("queued", 0)
    with running(worker_command(CHECKS), env):
        wait_until(lambda: _done(j1.id), "J1 is done")

    assert job_row(j1.id) == ("completed", 0)
    assert exceptions_on(b2) == [("duplicate", b1)]


def test_us6_three_failures_fail_b2_and_dead_letter(committed_db, queues):
    b1 = add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    j1 = start_job([b1, b2])
    _publish()
    env = process_env(queues, CHECK_LOCK_TIMEOUT_MS="200")

    with transaction.atomic(using="owner"), connections["owner"].cursor() as cursor:
        # An open insert of B2's exception key makes each check of B2 hit the lock timeout.
        cursor.execute(HOLD_EXCEPTION_KEY, [T1, b2, str(b1), b1])
        with running(worker_command(CHECKS), env):
            wait_until(lambda: _done(j1.id), "J1 is done")
            wait_until(
                lambda: queue_stats(queues, dead_letter_name(CHECKS)).ready == 1,
                "B2's message is in the DLQ",
            )
        transaction.set_rollback(True, using="owner")

    assert job_row(j1.id) == ("completed", 1)
    assert dead_letter_retries(queues, dead_letter_name(CHECKS)) == 2
    assert (
        owner_count(
            "check_job_bill",
            "job_id = %s AND bill_id = %s AND result = 'failed' AND error = 'OperationalError'",
            [j1.id, b2],
        )
        == 1
    )
    assert exceptions_on(b2) == []
