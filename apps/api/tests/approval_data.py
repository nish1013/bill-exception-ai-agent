from collections.abc import Callable
from typing import Any
from uuid import UUID

from django.db import connections, transaction

from payables.adapters.orm.audit import AuditOrmLog
from payables.adapters.orm.exceptions import ExceptionOrmRepository, ResolutionOrmRepository
from payables.adapters.orm.outbox import OutboxOrmRepository
from payables.adapters.orm.proposals import ProposalOrmRepository
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.proposals import (
    approve_fix_proposal,
    reject_fix_proposal,
    request_fix_proposal,
)
from payables.domain.access import Principal, Role
from payables.domain.errors import PayablesError
from payables.domain.proposals.agent import DraftOutcome
from payables.domain.proposals.proposals import ActionKind, DraftAction
from tests.check_data import C1
from tests.concurrency import owner_count
from tests.proposal_data import AlwaysAllow
from tests.tenants import T1

A1 = Principal(T1, Role.APPROVER, "a1")
A2 = Principal(T1, Role.APPROVER, "a2")


def drafting_proposal(exception_ids: list[UUID], requested_by: Principal = C1) -> UUID:
    with tenant_transaction(requested_by.tenant_id):
        tenant_id = requested_by.tenant_id
        return request_fix_proposal(
            requested_by,
            exception_ids,
            AlwaysAllow(),
            ExceptionOrmRepository(tenant_id),
            ProposalOrmRepository(tenant_id),
            OutboxOrmRepository(tenant_id),
        )


def pending_proposal(
    exception_ids: list[UUID], bill_id: UUID, requested_by: Principal = C1
) -> UUID:
    """A proposal that the agent drafted with one hold on the bill."""
    proposal_id = drafting_proposal(exception_ids, requested_by)
    outcome = DraftOutcome([DraftAction(ActionKind.HOLD, bill_id)], None, [])
    with tenant_transaction(requested_by.tenant_id):
        ProposalOrmRepository(requested_by.tenant_id).finish_draft(proposal_id, outcome)
    return proposal_id


def approve(approver: Principal, proposal_id: UUID) -> Callable[[], Any]:
    def call() -> Any:
        tenant_id = approver.tenant_id
        return _as_request(
            lambda: approve_fix_proposal(
                approver,
                proposal_id,
                ProposalOrmRepository(tenant_id),
                ResolutionOrmRepository(tenant_id),
                AuditOrmLog(tenant_id),
                OutboxOrmRepository(tenant_id),
                transaction.atomic,
            )
        )

    return call


def reject(approver: Principal, proposal_id: UUID, reason: str) -> Callable[[], Any]:
    def call() -> Any:
        tenant_id = approver.tenant_id
        return _as_request(
            lambda: reject_fix_proposal(
                approver,
                proposal_id,
                reason,
                ProposalOrmRepository(tenant_id),
                AuditOrmLog(tenant_id),
            )
        )

    return call


def now(call: Callable[[], Any], tenant_id: UUID = T1) -> Any:
    with tenant_transaction(tenant_id):
        return call()


def proposal_state(proposal_id: UUID) -> tuple[str, str | None, str | None]:
    return _rows(
        "SELECT status, approved_by, reject_reason FROM proposal WHERE id = %s", [proposal_id]
    )[0]


def proposal_resolutions(exception: UUID) -> list[tuple[str, str, UUID | None]]:
    return _rows(
        "SELECT kind, actor, proposal_id FROM resolution WHERE exception_id = %s", [exception]
    )


def apply_messages(proposal_id: UUID) -> int:
    return owner_count(
        "outbox",
        "command = 'ApplyFixProposal' AND payload->>'proposal_id' = %s",
        [str(proposal_id)],
    )


def _rows(sql: str, params: list) -> list[tuple]:
    with connections["owner"].cursor() as cursor:
        cursor.execute(sql, params)
        return [tuple(row) for row in cursor.fetchall()]


def _as_request(run: Callable[[], None]) -> PayablesError | None:
    # The GraphQL view commits the writes of an error that keeps them, and rolls back the rest.
    try:
        run()
    except PayablesError as error:
        if not error.keeps_writes:
            raise
        return error
    return None
