from collections.abc import Sequence
from typing import Protocol

from payables.domain.checks.jobs import CheckBill
from payables.domain.proposals.proposals import DraftFixProposal
from payables.domain.purchase_orders import PurchaseOrderAdded

type Message = CheckBill | PurchaseOrderAdded | DraftFixProposal


class Outbox(Protocol):
    def add(self, messages: Sequence[Message]) -> None: ...
