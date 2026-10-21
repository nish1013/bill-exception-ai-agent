import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from django.db import connection, connections

from payables.adapters.orm.tenants import tenant_transaction

TIMEOUT_SECONDS = 10


@dataclass
class RaceResult:
    first: Any = None
    second: Any = None
    errors: list[BaseException] = field(default_factory=list)


def race(tenant_id: UUID, first: Callable[[], Any], second: Callable[[], Any]) -> RaceResult:
    """Run first and keep its transaction open. Run second on another connection.

    first commits only when second waits on a lock or has finished. With the guard in place,
    second waits on first's uncommitted key. With the guard removed, second writes at once.
    """
    result = RaceResult()
    first_wrote = threading.Event()
    release = threading.Event()
    second_pid: list[int] = []

    def run_first() -> None:
        try:
            with tenant_transaction(tenant_id):
                result.first = first()
                first_wrote.set()
                release.wait(TIMEOUT_SECONDS)
        except BaseException as error:
            result.errors.append(error)
        finally:
            first_wrote.set()
            connections.close_all()

    def run_second() -> None:
        try:
            with tenant_transaction(tenant_id):
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    second_pid.append(cursor.fetchone()[0])
                result.second = second()
        except BaseException as error:
            result.errors.append(error)
        finally:
            connections.close_all()

    first_thread = threading.Thread(target=run_first)
    second_thread = threading.Thread(target=run_second)
    first_thread.start()
    first_wrote.wait(TIMEOUT_SECONDS)
    second_thread.start()
    _wait_until_blocked_or_done(second_thread, second_pid)
    release.set()
    first_thread.join(TIMEOUT_SECONDS)
    second_thread.join(TIMEOUT_SECONDS)
    return result


def owner_count(table: str, where: str = "TRUE", params: list | None = None) -> int:
    with connections["owner"].cursor() as cursor:
        cursor.execute(f"SELECT count(*) FROM {table} WHERE {where}", params or [])
        return cursor.fetchone()[0]


def _wait_until_blocked_or_done(thread: threading.Thread, pid: list[int]) -> None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if not thread.is_alive() or (pid and _waits_on_lock(pid[0])):
            return
        time.sleep(0.01)
    raise TimeoutError("the second transaction neither finished nor waited on a lock")


def _waits_on_lock(pid: int) -> bool:
    with connections["owner"].cursor() as cursor:
        cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [pid])
        row = cursor.fetchone()
    return row is not None and row[0] == "Lock"
