from typing import Protocol
from uuid import UUID

from payables.domain.checks.bill_check_completed import BillCheckCompleted
from payables.domain.checks.bill_check_progress import BillCheckProgress

type ConsoleEvent = BillCheckProgress | BillCheckCompleted


class ConsoleEvents(Protocol):
    def publish(self, tenant_id: UUID, event: ConsoleEvent) -> None: ...
