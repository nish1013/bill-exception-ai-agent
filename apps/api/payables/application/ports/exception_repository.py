from typing import Protocol
from uuid import UUID

from payables.domain.checks.exceptions import StoredException
from payables.domain.checks.rules import Finding, Rule


class ExceptionRepository(Protocol):
    def add_missing(self, bill_id: UUID, findings: list[Finding]) -> None: ...

    def on_bill(self, bill_id: UUID) -> list[StoredException]: ...

    def exists(self, exception_id: UUID) -> bool: ...

    def bills_with_open(self, rule: Rule, fingerprint: str) -> list[UUID]: ...
