from typing import Protocol
from uuid import UUID

from payables.domain.checks.jobs import BillCheckCompleted, BillCheckProgress

type ConsoleEvent = BillCheckProgress | BillCheckCompleted


class ConsoleEvents(Protocol):
    def publish(self, tenant_id: UUID, event: ConsoleEvent) -> None: ...
