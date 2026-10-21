from typing import Protocol
from uuid import UUID

from payables.domain.checks.rules import CheckedBill


class CheckedBillRepository(Protocol):
    def existing_ids(self, bill_ids: list[UUID]) -> set[UUID]: ...

    def get(self, bill_id: UUID) -> CheckedBill: ...

    def earlier_alike(self, bill: CheckedBill) -> list[CheckedBill]: ...
