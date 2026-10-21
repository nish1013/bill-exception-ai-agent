import time
from uuid import uuid4

import pytest
from asgiref.sync import async_to_sync, sync_to_async

from payables.adapters.channels.channels_console_events import ChannelsConsoleEvents
from payables.domain.checks.jobs import BillCheckProgress
from payables.entrypoints.ws import events_consumer
from tests.socket import events_socket
from tests.tenants import T1, T2

# The consumer closes old database connections on each message, as Django does per request.
pytestmark = pytest.mark.usefixtures("committed_db")

QUIET_SECONDS = 0.5
J1 = uuid4()
J8 = uuid4()


def _progress(job_id, seq: int = 3, percent: int = 40) -> BillCheckProgress:
    return BillCheckProgress(job_id, seq, percent)


async def _connected(token: str):
    socket = events_socket(token)
    connected = await socket.connect()
    assert connected
    return socket


async def _publish(tenant_id, event) -> None:
    # The worker publishes from sync code. The test calls the same adapter from a thread.
    await sync_to_async(ChannelsConsoleEvents().publish)(tenant_id, event)


def test_us7_t1_socket_gets_t1_progress(token_for):
    token = token_for("c1")

    async def scenario():
        socket = await _connected(token)
        await _publish(T1, _progress(J1))
        message = await socket.receive_json_from(timeout=5)
        await socket.disconnect()
        return message

    assert async_to_sync(scenario)() == {
        "type": "BillCheckProgress",
        "jobId": str(J1),
        "seq": 3,
        "percent": 40,
    }


def test_us7_t2_socket_gets_no_t1_event(token_for):
    c1, c9 = token_for("c1"), token_for("c9")

    async def scenario():
        t1_socket, t2_socket = await _connected(c1), await _connected(c9)
        await _publish(T1, _progress(J1))
        await _publish(T2, _progress(J8, seq=1, percent=10))
        t1_messages = [await t1_socket.receive_json_from(timeout=5)]
        t2_messages = [await t2_socket.receive_json_from(timeout=5)]
        t2_quiet = await t2_socket.receive_nothing(timeout=QUIET_SECONDS)
        t1_quiet = await t1_socket.receive_nothing(timeout=QUIET_SECONDS)
        await t1_socket.disconnect()
        await t2_socket.disconnect()
        return t1_messages, t2_messages, t1_quiet and t2_quiet

    t1_messages, t2_messages, quiet = async_to_sync(scenario)()

    assert [m["jobId"] for m in t1_messages] == [str(J1)]
    assert [m["jobId"] for m in t2_messages] == [str(J8)]
    assert quiet


@pytest.mark.parametrize("user", [None, "no-tenant", "bad-signature"])
def test_us7_socket_without_valid_token_refused(token_for, user):
    token = {None: None, "no-tenant": token_for("no-tenant")}.get(user)
    if user == "bad-signature":
        header, payload, _ = token_for("c1").split(".")
        token = f"{header}.{payload}.c2lnbmF0dXJl"

    async def scenario():
        socket = events_socket(token)
        connected = await socket.connect()
        await socket.disconnect()
        return connected

    assert async_to_sync(scenario)() is False


def test_us7_socket_closes_on_first_event_after_token_expiry(token_for, monkeypatch):
    token = token_for("c1")

    async def scenario():
        socket = await _connected(token)
        monkeypatch.setattr(events_consumer, "now", lambda: time.time() + 7200)
        await _publish(T1, _progress(J1))
        output = await socket.receive_output(timeout=5)
        await socket.disconnect()
        return output

    assert async_to_sync(scenario)() == {"type": "websocket.close", "code": 4401}
