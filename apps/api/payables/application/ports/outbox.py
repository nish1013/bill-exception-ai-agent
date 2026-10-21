from collections.abc import Sequence
from typing import Protocol

from payables.domain.checks.jobs import CheckBill
from payables.domain.purchase_orders import PurchaseOrderAdded

type Message = CheckBill | PurchaseOrderAdded


class Outbox(Protocol):
    def add(self, messages: Sequence[Message]) -> None: ...
