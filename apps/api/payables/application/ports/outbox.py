from collections.abc import Sequence
from typing import Protocol

from payables.domain.checks.check_bill_command import CheckBill


class Outbox(Protocol):
    def add(self, commands: Sequence[CheckBill]) -> None: ...
