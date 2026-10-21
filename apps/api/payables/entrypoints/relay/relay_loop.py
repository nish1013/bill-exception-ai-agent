import logging
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from django.db import close_old_connections

from payables.adapters.outbox.relay import BATCH_SIZE, OutboxRelay
from payables.entrypoints.relay.sweeper import sweep_stale_check_jobs

logger = logging.getLogger(__name__)

PUBLISH_EVERY_SECONDS = 1.0
SWEEP_EVERY_SECONDS = 30.0
CLEAN_EVERY_SECONDS = 3600.0


@dataclass
class Chore:
    name: str
    every_seconds: float
    run: Callable[[], int]
    next_at: float = 0.0


class RelayLoop:
    def __init__(self, relay: OutboxRelay) -> None:
        self._stop = threading.Event()
        self._chores = [
            Chore("sweep", SWEEP_EVERY_SECONDS, sweep_stale_check_jobs),
            Chore("clean", CLEAN_EVERY_SECONDS, relay.delete_sent),
        ]
        self._relay = relay

    def run(self) -> None:
        signal.signal(signal.SIGTERM, lambda *_: self._stop.set())
        signal.signal(signal.SIGINT, lambda *_: self._stop.set())
        logger.info("outbox relay started")
        while not self._stop.is_set():
            self._guarded("publish", self._publish_all)
            now = time.monotonic()
            for chore in self._chores:
                if now >= chore.next_at:
                    self._guarded(chore.name, chore.run)
                    chore.next_at = now + chore.every_seconds
            self._stop.wait(PUBLISH_EVERY_SECONDS)
        logger.info("outbox relay stopped")

    def _publish_all(self) -> int:
        total = 0
        while (sent := self._relay.publish_pending()) == BATCH_SIZE:
            total += sent
        return total + sent

    def _guarded(self, name: str, run: Callable[[], int]) -> None:
        # A broker or database outage must not stop the relay. The next tick tries again.
        try:
            close_old_connections()
            count = run()
        except Exception:
            logger.exception("relay %s failed", name)
            return
        if count:
            logger.info("relay %s: %d", name, count)
