from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from payables.domain.errors import ValidationError
from payables.domain.proposals.proposals import ActionKind, ProposalStatus

# The worker tries 5 times, with backoff from 10 s. Then the proposal is sync_failed (D9).
MAX_APPLY_ATTEMPTS = 5
FIRST_RETRY_SECONDS = 10

# The worker starts an apply only for a proposal in one of these statuses. A repeat delivery for
# a synced proposal, or a late delivery for a sync_failed one, changes nothing (D42).
APPLICABLE_STATUSES = (ProposalStatus.APPROVED, ProposalStatus.SYNCING)


class ActionStatus(StrEnum):
    PENDING = "pending"
    # Accounting has the action and confirms it later by callback (US16).
    ACCEPTED = "accepted"
    SYNCED = "synced"


class SyncAnswer(StrEnum):
    SYNCED = "synced"
    ACCEPTED = "accepted"


class CallbackStatus(StrEnum):
    SUCCEEDED = "succeeded"


@dataclass(frozen=True)
class SyncAction:
    """What accounting gets for one action. The sync key makes a repeat send safe (D8)."""

    tenant_id: UUID
    sync_key: UUID
    kind: ActionKind
    bill_id: UUID
    supplier_name: str
    invoice_number: str
    po_number: str | None


@dataclass(frozen=True)
class SyncResult:
    sync_key: UUID
    answer: SyncAnswer | None

    @property
    def failed(self) -> bool:
        return self.answer is None


@dataclass(frozen=True)
class SyncCallback:
    sync_key: UUID
    status: CallbackStatus

    @classmethod
    def parse(cls, raw: object) -> "SyncCallback":
        if not isinstance(raw, dict):
            raise ValidationError("a callback body is a JSON object")
        try:
            return cls(UUID(str(raw["sync_key"])), CallbackStatus(raw["status"]))
        except (KeyError, ValueError) as error:
            raise ValidationError("a callback needs sync_key and status") from error


@dataclass(frozen=True)
class ProposalSyncChanged:
    proposal_id: UUID
    status: ProposalStatus


def action_status_after(answer: SyncAnswer) -> ActionStatus:
    return ActionStatus(answer.value)


def synced_when_all(statuses: Iterable[ActionStatus]) -> bool:
    # A proposal is synced only when each of its actions is synced (I11).
    listed = list(statuses)
    return bool(listed) and all(status is ActionStatus.SYNCED for status in listed)


def is_last_attempt(retries_done: int) -> bool:
    return retries_done >= MAX_APPLY_ATTEMPTS - 1


def retry_delay_seconds(
    retries_done: int, first_retry_seconds: float = FIRST_RETRY_SECONDS
) -> float:
    return first_retry_seconds * 2**retries_done
