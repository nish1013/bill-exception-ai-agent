import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from django.db import connections

from payables.adapters.orm.exceptions import ExceptionOrmRepository
from payables.adapters.orm.outbox import OutboxOrmRepository
from payables.adapters.orm.proposals import ProposalOrmRepository
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.proposals import request_fix_proposal
from payables.domain.proposals.agent import ModelMessage, ModelReply, ToolCall, ToolSpec
from tests.check_data import CLERKS, add_bill, check, exception_id, start_job
from tests.tenants import T1

TODAY = "(now() AT TIME ZONE 'UTC')::date"

SEED_SLOTS = f"""
INSERT INTO proposal (id, tenant_id, requested_by, status, quota_day, quota_slot, created_at,
                      updated_at)
SELECT gen_random_uuid(), %s, 'c1', 'pending', {TODAY} + %s, slot, now(), now()
FROM generate_series(1, %s) AS slot
"""


class AlwaysAllow:
    def allow(self, tenant_id: UUID) -> bool:
        return True


def open_exception(key: str, tenant_id: UUID = T1, **changes) -> tuple[UUID, UUID]:
    """A bill with no receipt and its open missing_receipt exception."""
    changes = {"invoice_number": f"INV-{key}", "has_receipt": False} | changes
    bill = add_bill(key, tenant_id=tenant_id, **changes)
    check(start_job([bill], tenant_id=tenant_id).id, bill, tenant_id=tenant_id)
    return bill, exception_id(bill, "missing_receipt")


def request(exception_ids: list[UUID], tenant_id: UUID = T1):
    def call() -> UUID:
        return request_fix_proposal(
            CLERKS[tenant_id],
            exception_ids,
            AlwaysAllow(),
            ExceptionOrmRepository(tenant_id),
            ProposalOrmRepository(tenant_id),
            OutboxOrmRepository(tenant_id),
        )

    return call


def request_now(exception_ids: list[UUID], tenant_id: UUID = T1) -> UUID:
    with tenant_transaction(tenant_id):
        return request(exception_ids, tenant_id)()


def seed_slots(count: int, tenant_id: UUID = T1, days_from_today: int = 0) -> None:
    with connections["owner"].cursor() as cursor:
        cursor.execute(SEED_SLOTS, [tenant_id, days_from_today, count])


def slots_today(tenant_id: UUID = T1) -> list[int]:
    return _rows(
        f"SELECT quota_slot FROM proposal WHERE tenant_id = %s AND quota_day = {TODAY} "
        "ORDER BY quota_slot",
        [tenant_id],
        single=True,
    )


def proposal_row(proposal_id: UUID) -> tuple[str, str | None]:
    return _rows("SELECT status, failed_reason FROM proposal WHERE id = %s", [proposal_id])[0]


def actions_of(proposal_id: UUID) -> list[tuple[str, UUID, str | None]]:
    return _rows(
        "SELECT kind, bill_id, po_number FROM proposal_action WHERE proposal_id = %s "
        "ORDER BY created_at, id",
        [proposal_id],
    )


def audit_of(proposal_id: UUID) -> list[tuple[str, str, dict[str, Any]]]:
    rows = _rows(
        "SELECT kind, actor, payload::text FROM audit WHERE proposal_id = %s "
        "ORDER BY created_at, kind",
        [proposal_id],
    )
    return [(kind, actor, json.loads(payload)) for kind, actor, payload in rows]


def audit_text(proposal_id: UUID, kind: str) -> str:
    return json.dumps([payload for k, _, payload in audit_of(proposal_id) if k == kind])


class ScriptedLlm:
    """Gives one scripted reply per model call, and records each input it gets."""

    def __init__(self, *replies: ModelReply) -> None:
        self.replies = list(replies)
        self.inputs: list[list[ModelMessage]] = []

    def complete(
        self, messages: Sequence[ModelMessage], tools: Sequence[ToolSpec], timeout_seconds: float
    ) -> ModelReply:
        self.inputs.append(list(messages))
        return self.replies.pop(0) if self.replies else ModelReply("Done.")

    def sent_text(self) -> str:
        return json.dumps([[m.content for m in messages] for messages in self.inputs])


def calls(*names_and_arguments: tuple[str, dict[str, Any]]) -> ModelReply:
    return ModelReply(
        "",
        tuple(
            ToolCall(f"call_{n}", name, arguments)
            for n, (name, arguments) in enumerate(names_and_arguments)
        ),
    )


def _rows(sql: str, params: list, single: bool = False) -> list:
    with connections["owner"].cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    return [row[0] for row in rows] if single else [tuple(row) for row in rows]
