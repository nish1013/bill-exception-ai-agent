from typing import Protocol
from uuid import UUID

from payables.domain.checks.finding import Finding
from payables.domain.checks.rule import Rule
from payables.domain.checks.stored_exception import StoredException


class ExceptionRepository(Protocol):
    def add_missing(self, bill_id: UUID, findings: list[Finding]) -> None: ...

    def on_bill(self, bill_id: UUID) -> list[StoredException]: ...

    def exists(self, exception_id: UUID) -> bool: ...

    def bills_with_open(self, rule: Rule, fingerprint: str) -> list[UUID]: ...
