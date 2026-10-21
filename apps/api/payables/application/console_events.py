from typing import Protocol
from uuid import UUID

from payables.domain.checks.jobs import BillCheckCompleted, BillCheckProgress
from payables.domain.proposals.proposals import FixProposalReady

type ConsoleEvent = BillCheckProgress | BillCheckCompleted | FixProposalReady


class ConsoleEvents(Protocol):
    def publish(self, tenant_id: UUID, event: ConsoleEvent) -> None: ...
