import base64
import os
import signal
import subprocess
import time
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings
from django.db import connections
from kombu import Connection

# Each xdist worker gets its own vhost, so no worker purges or takes the messages of another.
TEST_VHOST = f"tests_{os.environ.get('PYTEST_XDIST_WORKER', 'main')}"
MANAGEMENT_PORT = 15672
WAIT_SECONDS = 30
STOP_SECONDS = 10


@dataclass(frozen=True)
class QueueStats:
    ready: int
    consumers: int


def test_vhost_url(broker_url: str) -> str:
    parts = urlsplit(broker_url)
    return parts._replace(path=f"/{TEST_VHOST}").geturl()


def create_vhost(broker_url: str) -> None:
    # The tests get their own vhost, so the Compose worker never takes a test message.
    parts = urlsplit(broker_url)
    base = f"http://{parts.hostname}:{MANAGEMENT_PORT}/api"
    auth = base64.b64encode(f"{parts.username}:{parts.password}".encode()).decode()
    for path, body in [
        (f"/vhosts/{TEST_VHOST}", b"{}"),
        (
            f"/permissions/{TEST_VHOST}/{parts.username}",
            b'{"configure": ".*", "write": ".*", "read": ".*"}',
        ),
    ]:
        request = urllib.request.Request(
            base + path,
            data=body,
            method="PUT",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
        )
        urllib.request.urlopen(request, timeout=5).close()


def queue_stats(broker_url: str, queue: str) -> QueueStats:
    with Connection(broker_url) as connection:
        _, ready, consumers = connection.default_channel.queue_declare(queue, passive=True)
    return QueueStats(ready, consumers)


def dead_letter_retries(broker_url: str, queue: str) -> int:
    with Connection(broker_url) as connection:
        message = connection.default_channel.basic_get(queue, no_ack=False)
        return message.headers["retries"]


def purge(broker_url: str, *queues: str) -> None:
    with Connection(broker_url) as connection:
        for queue in queues:
            connection.default_channel.queue_purge(queue)


def wait_until(condition: Callable[[], bool], what: str, seconds: float = WAIT_SECONDS) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.1)
    raise TimeoutError(f"timed out waiting until {what}")


def process_env(broker_url: str, **extra: str) -> dict[str, str]:
    return os.environ | {
        "POSTGRES_DB": connections["owner"].settings_dict["NAME"],
        "CELERY_BROKER_URL": broker_url,
        "CHANNEL_LAYER_PREFIX": settings.CHANNEL_LAYERS["default"]["CONFIG"]["prefix"],
        **extra,
    }


@contextmanager
def running(command: list[str], env: dict[str, str]) -> Iterator[subprocess.Popen]:
    process = subprocess.Popen(command, env=env, start_new_session=True)
    try:
        yield process
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(STOP_SECONDS)


def worker_command(queue: str) -> list[str]:
    # The solo pool runs the task in the worker process, so SIGKILL stops the task with it.
    return [
        "celery", "-A", "config", "worker", "-Q", queue, "-P", "solo", "-c", "1",
        "--without-gossip", "--without-mingle", "--without-heartbeat", "-l", "warning",
    ]  # fmt: skip


RELAY_COMMAND = ["python", "manage.py", "run_relay"]


def lock_waiters(database: str) -> int:
    with connections["owner"].cursor() as cursor:
        # Inside a transaction, Postgres keeps the first read of pg_stat_activity until cleared.
        cursor.execute("SELECT pg_stat_clear_snapshot()")
        cursor.execute(
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname = %s AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()",
            [database],
        )
        return cursor.fetchone()[0]
