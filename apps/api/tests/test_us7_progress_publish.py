import logging
from uuid import UUID

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from channels_redis.core import RedisChannelLayer

from payables.adapters.channels import ChannelsConsoleEvents
from payables.application.checks import ConsoleEvent
from payables.domain.checks.jobs import BillCheckProgress
from payables.entrypoints import tasks as check_bill_entrypoint
from payables.entrypoints.tasks import check_bill_task
from tests.check_data import add_bill, check, start_job
from tests.concurrency import owner_count
from tests.socket import events_socket
from tests.tenants import T1

pytestmark = pytest.mark.usefixtures("po_100")

CHECK_JOB = (
    "query($id: UUID!) { checkJob(id: $id) { status billCount okCount failedCount seq percent } }"
)


class CommittedRecorder:
    """Records each event with the checked count that another connection sees at that time."""

    def __init__(self) -> None:
        self.events: list[tuple[ConsoleEvent, int]] = []

    def publish(self, tenant_id: UUID, event: ConsoleEvent) -> None:
        committed = owner_count(
            "check_job_bill", "job_id = %s AND result <> 'pending'", [event.job_id]
        )
        self.events.append((event, committed))


def _run_task(job_id: UUID, bill_id: UUID) -> None:
    check_bill_task.apply(
        kwargs={"tenant_id": str(T1), "job_id": str(job_id), "bill_id": str(bill_id)}
    )


@pytest.fixture
def recorder(monkeypatch) -> CommittedRecorder:
    recorder = CommittedRecorder()
    monkeypatch.setattr(check_bill_entrypoint, "ChannelsConsoleEvents", lambda: recorder)
    return recorder


def test_d18_event_sent_after_the_result_commits(committed_db, recorder):
    b1, b2 = add_bill("K1"), add_bill("K2", invoice_number="INV-002")
    j1 = start_job([b1, b2])

    _run_task(j1.id, b1)
    _run_task(j1.id, b2)

    assert [(type(e).__name__, e.seq, committed) for e, committed in recorder.events] == [
        ("BillCheckProgress", 1, 1),
        ("BillCheckProgress", 2, 2),
        ("BillCheckCompleted", 2, 2),
    ]


def test_d42_repeat_delivery_sends_no_event(committed_db, recorder):
    b1 = add_bill("K1")
    j1 = start_job([b1])
    _run_task(j1.id, b1)
    recorder.events.clear()

    _run_task(j1.id, b1)

    assert recorder.events == []


def test_us7_worker_progress_reaches_the_t1_socket(committed_db, token_for):
    b1, b2 = add_bill("K1"), add_bill("K2", invoice_number="INV-002")
    j1 = start_job([b1, b2])
    token = token_for("c1")

    async def scenario():
        socket = events_socket(token)
        assert await socket.connect()
        await sync_to_async(_run_task)(j1.id, b1)
        await sync_to_async(_run_task)(j1.id, b2)
        messages = [await socket.receive_json_from() for _ in range(3)]
        await socket.disconnect()
        return messages

    assert async_to_sync(scenario)() == [
        {"type": "BillCheckProgress", "jobId": str(j1.id), "seq": 1, "percent": 50},
        {"type": "BillCheckProgress", "jobId": str(j1.id), "seq": 2, "percent": 100},
        {
            "type": "BillCheckCompleted",
            "jobId": str(j1.id),
            "seq": 2,
            "status": "completed",
            "failedCount": 0,
        },
    ]


def test_d18_redis_down_logs_and_keeps_the_result(committed_db, caplog):
    unreachable = RedisChannelLayer(hosts=["redis://127.0.0.1:1/0"])
    event = BillCheckProgress(UUID(int=1), 1, 50)

    with caplog.at_level(logging.WARNING):
        ChannelsConsoleEvents(unreachable).publish(T1, event)

    assert "console event not sent" in caplog.text


def test_d18_reconnect_reads_completed_from_the_job_row(committed_db, graphql, token_for):
    b1, b2 = add_bill("K1"), add_bill("K2", invoice_number="INV-002")
    j1 = start_job([b1, b2])
    check(j1.id, b1)
    check(j1.id, b2)

    response = graphql(CHECK_JOB, token_for("c1"), {"id": str(j1.id)})

    assert response.json()["data"]["checkJob"] == {
        "status": "completed",
        "billCount": 2,
        "okCount": 2,
        "failedCount": 0,
        "seq": 2,
        "percent": 100,
    }
