from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from payables.domain.checks.rules import Finding, Rule
from payables.domain.errors import ValidationError

MAX_LENGTH = 1000


class ResolutionKind(StrEnum):
    IGNORE = "ignore"
    SYSTEM = "system"
    PROPOSAL = "proposal"


class ExceptionStatus(StrEnum):
    OPEN = "open"
    IGNORED = "ignored"
    RESOLVED = "resolved"
    PENDING_SYNC = "pending_sync"

    @classmethod
    def parse(cls, value: str) -> "ExceptionStatus":
        try:
            return cls(value)
        except ValueError as error:
            raise ValidationError(f"status {value!r} is not known") from error


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def parse(cls, value: str) -> "Severity":
        try:
            return cls(value)
        except ValueError as error:
            raise ValidationError(f"severity {value!r} is not known") from error


# Status is derived on read from the resolution and its proposal (D38). No resolution: open.
RESOLUTION_STATUS: dict[ResolutionKind, ExceptionStatus] = {
    ResolutionKind.IGNORE: ExceptionStatus.IGNORED,
    ResolutionKind.SYSTEM: ExceptionStatus.RESOLVED,
}
# Money is safe only when accounting has the action. Until then the exception waits (D10).
PROPOSAL_SYNCED_STATUS = ExceptionStatus.RESOLVED
PROPOSAL_UNSYNCED_STATUS = ExceptionStatus.PENDING_SYNC

# A duplicate or a PO mismatch pays the wrong money. The others are a tax or paper risk (D27).
RULE_SEVERITY: dict[Rule, Severity] = {
    Rule.DUPLICATE: Severity.HIGH,
    Rule.PO_MISMATCH: Severity.HIGH,
    Rule.POSSIBLE_DUPLICATE: Severity.MEDIUM,
    Rule.MISSING_VAT: Severity.MEDIUM,
    Rule.MISSING_RECEIPT: Severity.LOW,
}

WORST_FIRST: tuple[Severity, ...] = (Severity.HIGH, Severity.MEDIUM, Severity.LOW)


@dataclass(frozen=True)
class StoredException:
    id: UUID
    rule: Rule
    fingerprint: str
    resolution: ResolutionKind | None

    @property
    def key(self) -> tuple[Rule, str]:
        return (self.rule, self.fingerprint)


@dataclass(frozen=True)
class ExceptionChanges:
    to_resolve: list[UUID]
    to_reopen: list[UUID]


@dataclass(frozen=True)
class IgnoreReason:
    text: str

    @classmethod
    def parse(cls, raw: str) -> "IgnoreReason":
        text = raw.strip()
        if not text:
            raise ValidationError("an ignore needs a reason")
        if len(text) > MAX_LENGTH:
            raise ValidationError(f"a reason has at most {MAX_LENGTH} characters")
        return cls(text)


def status_of(kind: ResolutionKind | None, proposal_synced: bool = False) -> ExceptionStatus:
    if kind is None:
        return ExceptionStatus.OPEN
    if kind is ResolutionKind.PROPOSAL:
        return PROPOSAL_SYNCED_STATUS if proposal_synced else PROPOSAL_UNSYNCED_STATUS
    return RESOLUTION_STATUS[kind]


def kinds_with(status: ExceptionStatus) -> list[ResolutionKind]:
    """The resolution kinds other than a proposal that give this status."""
    return [kind for kind, kind_status in RESOLUTION_STATUS.items() if kind_status is status]


def severity_of(rule: Rule) -> Severity:
    return RULE_SEVERITY[rule]


def rules_with(severity: Severity) -> list[Rule]:
    return [rule for rule, rule_severity in RULE_SEVERITY.items() if rule_severity is severity]


def changes_after_check(
    findings: Iterable[Finding], stored: Iterable[StoredException]
) -> ExceptionChanges:
    found = {finding.key for finding in findings}
    to_resolve: list[UUID] = []
    to_reopen: list[UUID] = []
    for exception in stored:
        if exception.key not in found and exception.resolution is None:
            # The problem is gone, so the system resolves it (D6).
            to_resolve.append(exception.id)
        elif exception.key in found and exception.resolution is ResolutionKind.SYSTEM:
            # The problem is back. Only a system resolve reopens: an ignore is final (D5, D29).
            to_reopen.append(exception.id)
    return ExceptionChanges(to_resolve=to_resolve, to_reopen=to_reopen)
