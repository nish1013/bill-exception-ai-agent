from collections.abc import Sequence
from typing import Protocol

from payables.domain.checks.check_bill_command import CheckBill
from payables.domain.purchase_order_added import PurchaseOrderAdded

type Message = CheckBill | PurchaseOrderAdded


class Outbox(Protocol):
    def add(self, messages: Sequence[Message]) -> None: ...
