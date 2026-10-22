from uuid import UUID

from django.db import connections
from django.test import Client

from payables.adapters.accounting import SIGNATURE_HEADER, CallbackSignature, StubAccounting
from payables.adapters.orm.proposals import ProposalOrmRepository, ProposalSyncOrmRepository
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.sync import (
    AccountingUnavailableError,
    ApplyOutcome,
    finish_apply,
    send_actions,
    start_apply,
)
from payables.domain.proposals.agent import DraftOutcome
from payables.domain.proposals.proposals import ActionKind, ApplyFixProposal, DraftAction
from payables.domain.proposals.sync import SyncAction, SyncAnswer, is_last_attempt
from tests.approval_data import A1, approve, drafting_proposal, now
from tests.concurrency import owner_count
from tests.tenants import T1

CALLBACK_SECRET = "test-callback-secret"
CALLBACK_PATH = "/callbacks/accounting/stub"

SET_STUB_MODE = """
INSERT INTO stub_mode (tenant_id, mode) VALUES (%s, %s)
ON CONFLICT (tenant_id) DO UPDATE SET mode = EXCLUDED.mode
"""


class RecordingCallbacks:
    def __init__(self) -> None:
        self.scheduled: list[UUID] = []

    def schedule(self, sync_key: UUID) -> None:
        self.scheduled.append(sync_key)


class FailingAccounting:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, action: SyncAction) -> SyncAnswer:
        self.calls += 1
        raise AccountingUnavailableError("accounting is down")


class CountingAccounting:
    def __init__(self, inner: StubAccounting) -> None:
        self.inner = inner
        self.calls = 0

    def send(self, action: SyncAction) -> SyncAnswer:
        self.calls += 1
        return self.inner.send(action)


def stub(mode: str = "ok", callbacks: RecordingCallbacks | None = None) -> StubAccounting:
    return StubAccounting(callbacks or RecordingCallbacks(), mode)


def drafted_proposal(exception_ids: list[UUID], actions: list[DraftAction]) -> UUID:
    proposal_id = drafting_proposal(exception_ids)
    with tenant_transaction(T1):
        ProposalOrmRepository(T1).finish_draft(proposal_id, DraftOutcome(actions, None, []))
    return proposal_id


def approved_proposal(exception_ids: list[UUID], *bills: UUID) -> UUID:
    """A proposal with one hold for each bill, approved by A1."""
    proposal_id = drafted_proposal(exception_ids, [DraftAction(ActionKind.HOLD, b) for b in bills])
    assert now(approve(A1, proposal_id)) is None
    return proposal_id


def apply_now(proposal_id: UUID, accounting, retries: int = 0) -> ApplyOutcome | None:
    """One delivery of ApplyFixProposal, in the same steps and transactions as the worker."""
    command = ApplyFixProposal(T1, proposal_id)
    proposals = ProposalSyncOrmRepository(T1)
    with tenant_transaction(T1):
        started = start_apply(command, proposals)
    if started is None:
        return None
    results = send_actions(started.actions, accounting)
    with tenant_transaction(T1):
        return finish_apply(command, results, is_last_attempt(retries), proposals)


def apply_until_done(proposal_id: UUID, accounting) -> int:
    """Delivers the message again while the worker asks for a retry. Returns the deliveries."""
    retries = 0
    while (outcome := apply_now(proposal_id, accounting, retries)) and outcome.retry:
        retries += 1
    return retries + 1


def set_stub_mode(mode: str, tenant_id: UUID = T1) -> None:
    with connections["owner"].cursor() as cursor:
        cursor.execute(SET_STUB_MODE, [tenant_id, mode])


def force_status(proposal_id: UUID, status: str) -> None:
    """Sets a status as the owner, with the approval fields that the status needs."""
    approved = status in ("approved", "syncing", "sync_failed", "synced")
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            "UPDATE proposal SET status = %s, approved_by = %s, approved_at = %s, "
            "reject_reason = %s WHERE id = %s",
            [
                status,
                "a1" if approved else None,
                "2026-10-22T00:00:00Z" if approved else None,
                "Wrong supplier" if status == "rejected" else None,
                proposal_id,
            ],
        )


def proposal_status(proposal_id: UUID) -> str:
    return _rows("SELECT status FROM proposal WHERE id = %s", [proposal_id])[0][0]


def actions_sync(proposal_id: UUID) -> list[tuple[UUID, str, int]]:
    return _rows(
        "SELECT sync_key, status, attempts FROM proposal_action WHERE proposal_id = %s "
        "ORDER BY created_at, id",
        [proposal_id],
    )


def sync_keys(proposal_id: UUID) -> list[UUID]:
    return [key for key, _, _ in actions_sync(proposal_id)]


def ledger_keys(tenant_id: UUID = T1) -> list[UUID]:
    rows = _rows("SELECT sync_key FROM stub_ledger WHERE tenant_id = %s", [tenant_id])
    return sorted(row[0] for row in rows)


def ledger_count(sync_key: UUID) -> int:
    return owner_count("stub_ledger", "sync_key = %s", [sync_key])


def callback_body(sync_key: UUID, status: str = "succeeded") -> bytes:
    return f'{{"sync_key": "{sync_key}", "status": "{status}"}}'.encode()


def post_callback(client: Client, body: bytes, signature: str | None = None, path=CALLBACK_PATH):
    headers = {}
    if signature is not None:
        headers["HTTP_" + SIGNATURE_HEADER.upper().replace("-", "_")] = signature
    return client.post(path, body, content_type="application/json", **headers)


def signed(body: bytes, secret: str = CALLBACK_SECRET) -> str:
    return CallbackSignature(secret).sign(body)


def _rows(sql: str, params: list) -> list[tuple]:
    with connections["owner"].cursor() as cursor:
        cursor.execute(sql, params)
        return [tuple(row) for row in cursor.fetchall()]
