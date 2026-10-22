import uuid

import pytest
from django.db import IntegrityError, ProgrammingError, connection, connections

from payables.adapters.orm.tenants import tenant_transaction
from payables.domain.proposals.proposals import ActionKind, DraftAction
from tests.proposal_data import open_exception
from tests.sync_data import (
    actions_sync,
    apply_now,
    approved_proposal,
    drafted_proposal,
    stub,
    sync_keys,
)
from tests.tenants import T1

pytestmark = pytest.mark.usefixtures("po_100")


def _as_app_role(sql: str, params: list) -> None:
    with tenant_transaction(T1), connection.cursor() as cursor:
        cursor.execute(sql, params)


def test_i10_app_role_cannot_change_a_sync_key(committed_db):
    b2, e1 = open_exception("K1")
    proposal = approved_proposal([e1], b2)
    keys = sync_keys(proposal)

    with pytest.raises(ProgrammingError, match="permission denied"):
        _as_app_role(
            "UPDATE proposal_action SET sync_key = %s WHERE proposal_id = %s",
            [uuid.uuid4(), proposal],
        )

    assert sync_keys(proposal) == keys


def test_i10_app_role_changes_only_status_and_attempts(committed_db):
    b2, e1 = open_exception("K1")
    proposal = approved_proposal([e1], b2)

    _as_app_role(
        "UPDATE proposal_action SET status = 'accepted', attempts = 1 WHERE proposal_id = %s",
        [proposal],
    )
    with pytest.raises(ProgrammingError, match="permission denied"):
        _as_app_role(
            "UPDATE proposal_action SET kind = 'credit' WHERE proposal_id = %s", [proposal]
        )

    assert [(status, attempts) for _, status, attempts in actions_sync(proposal)] == [
        ("accepted", 1)
    ]


def test_i10_two_actions_cannot_share_a_sync_key(committed_db):
    b2, e1 = open_exception("K1")
    proposal = drafted_proposal([e1], [DraftAction(ActionKind.HOLD, b2)])
    key = sync_keys(proposal)[0]

    with pytest.raises(IntegrityError), connections["owner"].cursor() as cursor:
        cursor.execute(
            "INSERT INTO proposal_action (id, tenant_id, proposal_id, kind, bill_id, sync_key, "
            "status, attempts, created_at) "
            "VALUES (%s, %s, %s, 'credit', %s, %s, 'pending', 0, now())",
            [uuid.uuid4(), T1, proposal, b2, key],
        )


def test_i10_the_stub_gets_the_key_that_the_action_stores(committed_db):
    b2, e1 = open_exception("K1")
    proposal = approved_proposal([e1], b2)
    keys = sync_keys(proposal)

    apply_now(proposal, stub("ok"))

    assert sync_keys(proposal) == keys
    with connections["owner"].cursor() as cursor:
        cursor.execute("SELECT sync_key FROM stub_ledger WHERE tenant_id = %s", [T1])
        assert [row[0] for row in cursor.fetchall()] == keys
