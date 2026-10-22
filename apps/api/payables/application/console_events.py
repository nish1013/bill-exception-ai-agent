from typing import Protocol
from uuid import UUID

from payables.domain.checks.jobs import BillCheckCompleted, BillCheckProgress
from payables.domain.proposals.proposals import FixProposalReady
from payables.domain.proposals.sync import ProposalSyncChanged

type ConsoleEvent = BillCheckProgress | BillCheckCompleted | FixProposalReady | ProposalSyncChanged


class ConsoleEvents(Protocol):
    def publish(self, tenant_id: UUID, event: ConsoleEvent) -> None: ...
