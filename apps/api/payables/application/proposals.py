from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from payables.application.authorization import require_role
from payables.application.console_events import ConsoleEvents
from payables.application.outbox import Outbox
from payables.application.pages import ListPage
from payables.domain.access import Principal, Role
from payables.domain.audit import AuditEntry
from payables.domain.checks.exceptions import ResolutionKind
from payables.domain.checks.rules import Rule
from payables.domain.errors import NotFoundError, RateLimitedError, ValidationError
from payables.domain.proposals.agent import (
    TOOL_SPECS,
    AgentRun,
    AgentTools,
    Clock,
    DraftOutcome,
    ModelMessage,
    ModelReply,
    ProposalScope,
    ToolSpec,
    assistant_message,
    failed_outcome,
    first_messages,
    redacted,
    tool_message,
)
from payables.domain.proposals.proposals import (
    REQUESTS_PER_MINUTE,
    ActionKind,
    DraftFixProposal,
    FailedReason,
    FixProposalReady,
    ProposalStatus,
    exceptions_to_fix,
)


@dataclass(frozen=True)
class ProposalExceptionItem:
    id: UUID
    rule: Rule
    invoice_number: str


@dataclass(frozen=True)
class ProposalActionItem:
    kind: ActionKind
    bill_id: UUID
    supplier_name: str
    invoice_number: str
    po_number: str | None


@dataclass(frozen=True)
class ProposalItem:
    id: UUID
    status: ProposalStatus
    requested_by: str
    quota_slot: int
    failed_reason: FailedReason | None
    created_at: datetime
    exceptions: list[ProposalExceptionItem]
    actions: list[ProposalActionItem]


class ProposalRepository(Protocol):
    def add(self, requested_by: str, exception_ids: list[UUID]) -> UUID: ...

    def draft_scope(self, proposal_id: UUID) -> ProposalScope | None: ...

    def finish_draft(self, proposal_id: UUID, outcome: DraftOutcome) -> ProposalStatus | None: ...


class ProposalQuery(Protocol):
    def find(self, proposal_id: UUID) -> ProposalItem | None: ...

    def latest(self, status: ProposalStatus | None) -> ListPage[ProposalItem]: ...


class ExceptionResolutions(Protocol):
    def resolutions(self, exception_ids: list[UUID]) -> dict[UUID, ResolutionKind | None]: ...


class AuditLog(Protocol):
    def add(self, proposal_id: UUID, entries: Sequence[AuditEntry]) -> None: ...


class RateLimiter(Protocol):
    def allow(self, tenant_id: UUID) -> bool: ...


class LlmPort(Protocol):
    def complete(
        self, messages: Sequence[ModelMessage], tools: Sequence[ToolSpec], timeout_seconds: float
    ) -> ModelReply: ...


def request_fix_proposal(
    principal: Principal,
    exception_ids: Iterable[UUID],
    rate_limiter: RateLimiter,
    exceptions: ExceptionResolutions,
    proposals: ProposalRepository,
    outbox: Outbox,
) -> UUID:
    require_role(principal, Role.CLERK)
    if not rate_limiter.allow(principal.tenant_id):
        raise RateLimitedError(f"at most {REQUESTS_PER_MINUTE} proposal requests in a minute")
    to_fix = exceptions_to_fix(exception_ids)
    resolutions = exceptions.resolutions(to_fix)
    if set(resolutions) != set(to_fix):
        raise NotFoundError("exception not found")
    if any(kind is not None for kind in resolutions.values()):
        raise ValidationError("a proposal takes open exceptions only")
    # The quota slot and the draft message commit with the proposal (I12, I14).
    proposal_id = proposals.add(principal.subject, to_fix)
    outbox.add([DraftFixProposal(principal.tenant_id, proposal_id)])
    return proposal_id


def get_proposal(proposal_id: UUID, proposals: ProposalQuery) -> ProposalItem:
    proposal = proposals.find(proposal_id)
    if proposal is None:
        raise NotFoundError("proposal not found")
    return proposal


def list_proposals(status: str | None, proposals: ProposalQuery) -> ListPage[ProposalItem]:
    return proposals.latest(None if status is None else ProposalStatus.parse(status))


def draft_scope(command: DraftFixProposal, proposals: ProposalRepository) -> ProposalScope | None:
    # A repeat delivery finds the proposal no longer drafting and stops (D42).
    return proposals.draft_scope(command.proposal_id)


def run_agent(scope: ProposalScope, llm: LlmPort, clock: Clock) -> DraftOutcome:
    run = AgentRun.start(clock)
    tools = AgentTools(scope)
    messages = first_messages()
    while True:
        if run.timed_out:
            return run.fail(FailedReason.TIMEOUT)
        sent = [redacted(message) for message in messages]
        run.record_input(sent)
        reply = llm.complete(sent, TOOL_SPECS, run.remaining_seconds)
        run.record_output(reply)
        if run.timed_out:
            return run.fail(FailedReason.TIMEOUT)
        if not reply.tool_calls:
            return run.finish()
        messages.append(assistant_message(reply))
        for call in reply.tool_calls:
            if not run.has_call_left():
                run.record_over_limit(call)
                return run.fail(FailedReason.MAX_TOOL_CALLS)
            result = tools.run(call)
            run.record_call(call, result)
            messages.append(tool_message(call, result))


def finish_draft(
    command: DraftFixProposal,
    outcome: DraftOutcome,
    proposals: ProposalRepository,
    audit: AuditLog,
) -> FixProposalReady | None:
    status = proposals.finish_draft(command.proposal_id, outcome)
    if status is None:
        return None
    audit.add(command.proposal_id, outcome.audit)
    return FixProposalReady(command.proposal_id, status)


def fail_draft(
    command: DraftFixProposal, proposals: ProposalRepository, audit: AuditLog
) -> FixProposalReady | None:
    # The last failed delivery makes the proposal failed, so the clerk never waits on it.
    return finish_draft(command, failed_outcome(FailedReason.ERROR), proposals, audit)


def publish_proposal_ready(tenant_id: UUID, ready: FixProposalReady, events: ConsoleEvents) -> None:
    events.publish(tenant_id, ready)
