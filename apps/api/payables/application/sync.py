import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from payables.application.authorization import require_role
from payables.application.console_events import ConsoleEvents
from payables.application.outbox import Outbox
from payables.application.pages import ListPage
from payables.domain.access import Principal, Role
from payables.domain.errors import ConflictError, NotFoundError
from payables.domain.proposals.proposals import ActionKind, ApplyFixProposal, ProposalStatus
from payables.domain.proposals.sync import (
    APPLICABLE_STATUSES,
    ActionStatus,
    ProposalSyncChanged,
    SyncAction,
    SyncAnswer,
    SyncCallback,
    SyncResult,
    synced_when_all,
)

logger = logging.getLogger(__name__)


class AccountingUnavailableError(Exception):
    """Accounting did not take the action. The worker tries again (D9)."""


@dataclass(frozen=True)
class ApplyStart:
    actions: list[SyncAction]
    changed: ProposalSyncChanged | None


@dataclass(frozen=True)
class ApplyOutcome:
    changed: ProposalSyncChanged | None
    retry: bool


@dataclass(frozen=True)
class LedgerEntry:
    sync_key: UUID
    kind: ActionKind
    supplier_name: str
    invoice_number: str
    po_number: str | None
    answer: SyncAnswer
    received_at: datetime


class AccountingSyncPort(Protocol):
    def send(self, action: SyncAction) -> SyncAnswer: ...


class SyncRepository(Protocol):
    def lock_status(self, proposal_id: UUID) -> ProposalStatus | None: ...

    def move(
        self, proposal_id: UUID, from_statuses: tuple[ProposalStatus, ...], to: ProposalStatus
    ) -> bool: ...

    def pending_actions(self, proposal_id: UUID) -> list[SyncAction]: ...

    def record_results(self, proposal_id: UUID, results: list[SyncResult]) -> None: ...

    def action_statuses(self, proposal_id: UUID) -> list[ActionStatus]: ...

    def proposal_of_key(self, sync_key: UUID) -> UUID | None: ...

    def mark_synced(self, sync_key: UUID) -> bool: ...


class LedgerQuery(Protocol):
    def latest(self) -> ListPage[LedgerEntry]: ...


def start_apply(command: ApplyFixProposal, proposals: SyncRepository) -> ApplyStart | None:
    proposal_id = command.proposal_id
    status = proposals.lock_status(proposal_id)
    if status not in APPLICABLE_STATUSES:
        return None
    changed = None
    if proposals.move(proposal_id, (ProposalStatus.APPROVED,), ProposalStatus.SYNCING):
        changed = ProposalSyncChanged(proposal_id, ProposalStatus.SYNCING)
    # An accepted action waits for its callback. Only a pending action goes to accounting.
    return ApplyStart(proposals.pending_actions(proposal_id), changed)


def send_actions(actions: list[SyncAction], accounting: AccountingSyncPort) -> list[SyncResult]:
    results: list[SyncResult] = []
    for action in actions:
        try:
            answer: SyncAnswer | None = accounting.send(action)
        except AccountingUnavailableError:
            logger.warning("accounting refused action %s", action.sync_key, exc_info=True)
            answer = None
        results.append(SyncResult(action.sync_key, answer))
    return results


def finish_apply(
    command: ApplyFixProposal,
    results: list[SyncResult],
    last_attempt: bool,
    proposals: SyncRepository,
) -> ApplyOutcome:
    proposal_id = command.proposal_id
    status = proposals.lock_status(proposal_id)
    proposals.record_results(proposal_id, results)
    if status is not ProposalStatus.SYNCING:
        return ApplyOutcome(None, retry=False)
    if synced_when_all(proposals.action_statuses(proposal_id)):
        return ApplyOutcome(_move(proposals, proposal_id, ProposalStatus.SYNCED), retry=False)
    if not any(result.failed for result in results):
        return ApplyOutcome(None, retry=False)
    if last_attempt:
        # The approve stays committed. An approver can retry (D9, D32).
        return ApplyOutcome(_move(proposals, proposal_id, ProposalStatus.SYNC_FAILED), retry=False)
    return ApplyOutcome(None, retry=True)


def fail_apply(command: ApplyFixProposal, proposals: SyncRepository) -> ProposalSyncChanged | None:
    proposals.lock_status(command.proposal_id)
    return _move(proposals, command.proposal_id, ProposalStatus.SYNC_FAILED)


def receive_sync_callback(
    callback: SyncCallback, proposals: SyncRepository
) -> ProposalSyncChanged | None:
    proposal_id = proposals.proposal_of_key(callback.sync_key)
    if proposal_id is None:
        raise NotFoundError("sync key not found")
    # Two callbacks for two actions queue on the lock, so the second sees the first (I11, D40).
    status = proposals.lock_status(proposal_id)
    if not proposals.mark_synced(callback.sync_key):
        return None
    if status is ProposalStatus.SYNCING and synced_when_all(proposals.action_statuses(proposal_id)):
        return _move(proposals, proposal_id, ProposalStatus.SYNCED)
    return None


def retry_sync(
    principal: Principal, proposal_id: UUID, proposals: SyncRepository, outbox: Outbox
) -> None:
    # A retry sends money actions again, so only an approver can start it (D32).
    require_role(principal, Role.APPROVER)
    status = proposals.lock_status(proposal_id)
    if status is None:
        raise NotFoundError("proposal not found")
    if not proposals.move(proposal_id, (ProposalStatus.SYNC_FAILED,), ProposalStatus.SYNCING):
        raise ConflictError("only a sync_failed proposal can be retried")
    # The new apply message commits with the status, and uses the same sync keys (D8, I14).
    outbox.add([ApplyFixProposal(principal.tenant_id, proposal_id)])


def list_ledger(ledger: LedgerQuery) -> ListPage[LedgerEntry]:
    return ledger.latest()


def publish_sync_changed(
    tenant_id: UUID, changed: ProposalSyncChanged | None, events: ConsoleEvents
) -> None:
    if changed is not None:
        events.publish(tenant_id, changed)


def _move(
    proposals: SyncRepository, proposal_id: UUID, to: ProposalStatus
) -> ProposalSyncChanged | None:
    if not proposals.move(proposal_id, (ProposalStatus.SYNCING,), to):
        return None
    return ProposalSyncChanged(proposal_id, to)
