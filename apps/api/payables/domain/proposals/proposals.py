from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from payables.domain.audit import AuditEntry, AuditKind
from payables.domain.errors import ForbiddenError, RateLimitedError, ValidationError

DAILY_QUOTA = 50
REQUESTS_PER_MINUTE = 5
# One list_exceptions call and one draft for each exception fit in the bound of 8 tool calls (D20).
MAX_EXCEPTIONS = 7
REJECT_REASON_MAX_LENGTH = 1000


class ProposalStatus(StrEnum):
    DRAFTING = "drafting"
    PENDING = "pending"
    FAILED = "failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    STALE = "stale"
    SYNCING = "syncing"
    SYNCED = "synced"
    SYNC_FAILED = "sync_failed"

    @classmethod
    def parse(cls, value: str) -> "ProposalStatus":
        try:
            return cls(value)
        except ValueError as error:
            raise ValidationError(f"status {value!r} is not known") from error


# Each status after an approve keeps its one approval (I9).
APPROVED_STATUSES = (
    ProposalStatus.APPROVED,
    ProposalStatus.SYNCING,
    ProposalStatus.SYNCED,
    ProposalStatus.SYNC_FAILED,
)


class FailedReason(StrEnum):
    MAX_TOOL_CALLS = "max_tool_calls"
    TIMEOUT = "timeout"
    NO_ACTIONS = "no_actions"
    ERROR = "error"


class ActionKind(StrEnum):
    HOLD = "hold"
    CREDIT = "credit"
    MATCH = "match"


@dataclass(frozen=True)
class DraftFixProposal:
    tenant_id: UUID
    proposal_id: UUID


@dataclass(frozen=True)
class ApplyFixProposal:
    tenant_id: UUID
    proposal_id: UUID


@dataclass(frozen=True)
class FixProposalReady:
    proposal_id: UUID
    status: ProposalStatus


@dataclass(frozen=True)
class DraftAction:
    kind: ActionKind
    bill_id: UUID
    po_number: str | None = None


@dataclass(frozen=True)
class QuotaSlot:
    number: int

    @classmethod
    def after(cls, highest_taken: int) -> "QuotaSlot":
        # Slot 51 does not exist, so the request is refused and takes nothing (D21, D36).
        if highest_taken >= DAILY_QUOTA:
            raise RateLimitedError(f"the tenant used {DAILY_QUOTA} of {DAILY_QUOTA} today")
        return cls(highest_taken + 1)


def exceptions_to_fix(exception_ids: Iterable[UUID]) -> list[UUID]:
    unique = list(dict.fromkeys(exception_ids))
    if not unique:
        raise ValidationError("a proposal needs at least one exception")
    if len(unique) > MAX_EXCEPTIONS:
        raise ValidationError(f"a proposal takes at most {MAX_EXCEPTIONS} exceptions")
    return unique


@dataclass(frozen=True)
class RejectReason:
    text: str

    @classmethod
    def parse(cls, raw: str) -> "RejectReason":
        text = raw.strip()
        if not text:
            raise ValidationError("a reject needs a reason")
        if len(text) > REJECT_REASON_MAX_LENGTH:
            raise ValidationError(f"a reason has at most {REJECT_REASON_MAX_LENGTH} characters")
        return cls(text)


def require_second_person(requested_by: str, approver: str) -> None:
    # Four-eyes: the requester never approves the same proposal (I9, D11).
    if requested_by == approver:
        raise ForbiddenError("an approver cannot approve a proposal they requested")


def approved_entry(approver: str, requested_by: str, exception_ids: list[UUID]) -> AuditEntry:
    return AuditEntry(
        AuditKind.APPROVED,
        approver,
        {"requested_by": requested_by, "exception_ids": [str(e) for e in exception_ids]},
    )


def rejected_entry(approver: str, reason: RejectReason) -> AuditEntry:
    return AuditEntry(AuditKind.REJECTED, approver, {"reason": reason.text})


def stale_entry(approver: str, exception_ids: list[UUID]) -> AuditEntry:
    return AuditEntry(AuditKind.STALE, approver, {"exception_ids": [str(e) for e in exception_ids]})
