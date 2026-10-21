from typing import Protocol
from uuid import UUID

from payables.domain.checks.finding import Finding


class ExceptionRepository(Protocol):
    def add_missing(self, bill_id: UUID, findings: list[Finding]) -> None: ...
