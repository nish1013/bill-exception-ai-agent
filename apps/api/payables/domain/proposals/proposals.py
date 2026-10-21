from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from payables.domain.errors import RateLimitedError, ValidationError

DAILY_QUOTA = 50
REQUESTS_PER_MINUTE = 5
# One list_exceptions call and one draft for each exception fit in the bound of 8 tool calls (D20).
MAX_EXCEPTIONS = 7


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
