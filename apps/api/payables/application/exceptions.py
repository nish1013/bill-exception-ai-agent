from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from payables.application.authorization import require_role
from payables.application.pages import ListPage
from payables.domain.access import Principal, Role
from payables.domain.checks.exceptions import (
    ExceptionStatus,
    IgnoreReason,
    Severity,
    StoredException,
)
from payables.domain.checks.rules import Finding, Rule
from payables.domain.errors import NotFoundError


@dataclass(frozen=True)
class InboxFilter:
    status: ExceptionStatus | None
    severity: Severity | None

    @classmethod
    def parse(cls, status: str | None, severity: str | None) -> "InboxFilter":
        return cls(
            status=None if status is None else ExceptionStatus.parse(status),
            severity=None if severity is None else Severity.parse(severity),
        )


@dataclass(frozen=True)
class InboxItem:
    id: UUID
    bill_id: UUID
    supplier_name: str
    invoice_number: str
    rule: Rule
    severity: Severity
    status: ExceptionStatus
    related_bill_id: UUID | None
    created_at: datetime
    resolved_by: str | None
    reason: str | None


class ExceptionRepository(Protocol):
    def add_missing(self, bill_id: UUID, findings: list[Finding]) -> None: ...

    def on_bill(self, bill_id: UUID) -> list[StoredException]: ...

    def exists(self, exception_id: UUID) -> bool: ...

    def bills_with_open(self, rule: Rule, fingerprint: str) -> list[UUID]: ...


class ResolutionRepository(Protocol):
    def ignore(self, exception_id: UUID, actor: str, reason: IgnoreReason) -> None: ...

    def resolve_by_system(self, exception_ids: list[UUID]) -> None: ...

    def reopen(self, exception_ids: list[UUID]) -> None: ...


class InboxQuery(Protocol):
    def worst_first(self, filters: InboxFilter) -> ListPage[InboxItem]: ...

    def find(self, exception_id: UUID) -> InboxItem | None: ...


def list_exceptions(filters: InboxFilter, inbox: InboxQuery) -> ListPage[InboxItem]:
    return inbox.worst_first(filters)


def get_exception(exception_id: UUID, inbox: InboxQuery) -> InboxItem:
    item = inbox.find(exception_id)
    if item is None:
        raise NotFoundError("exception not found")
    return item


def ignore_exception(
    principal: Principal,
    exception_id: UUID,
    reason: str,
    exceptions: ExceptionRepository,
    resolutions: ResolutionRepository,
) -> None:
    require_role(principal, Role.CLERK)
    parsed = IgnoreReason.parse(reason)
    if not exceptions.exists(exception_id):
        raise NotFoundError("exception not found")
    # The key on the exception id refuses a second resolution with a conflict (I7).
    resolutions.ignore(exception_id, principal.subject, parsed)
