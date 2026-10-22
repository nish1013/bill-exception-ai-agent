import pytest

from tests.approval_data import apply_messages, pending_proposal
from tests.check_data import C9
from tests.ingest_data import error_of
from tests.proposal_data import open_exception
from tests.sync_data import (
    FailingAccounting,
    apply_now,
    apply_until_done,
    approved_proposal,
    force_status,
    ledger_keys,
    proposal_status,
    stub,
    sync_keys,
)

pytestmark = pytest.mark.usefixtures("po_100")

RETRY = "mutation($id: UUID!) { retrySync(proposalId: $id) { id status } }"


@pytest.fixture
def sync_failed_p1(committed_db):
    b2, e1 = open_exception("K1")
    proposal = approved_proposal([e1], b2)
    apply_until_done(proposal, FailingAccounting())
    assert proposal_status(proposal) == "sync_failed"
    return proposal


def _retry(graphql, token_for, proposal, user="a1"):
    return graphql(RETRY, token_for(user), {"id": str(proposal)})


def test_us15_a1_retries_sync_failed_p1_syncing_new_apply_job(sync_failed_p1, graphql, token_for):
    keys = sync_keys(sync_failed_p1)

    response = _retry(graphql, token_for, sync_failed_p1)

    assert response.json()["data"]["retrySync"]["status"] == "syncing"
    assert proposal_status(sync_failed_p1) == "syncing"
    assert apply_messages(sync_failed_p1) == 2
    apply_now(sync_failed_p1, stub("ok"))
    assert proposal_status(sync_failed_p1) == "synced"
    assert sync_keys(sync_failed_p1) == keys
    assert ledger_keys() == keys


def test_us15_synced_p1_retry_409(committed_db, graphql, token_for):
    b2, e1 = open_exception("K1")
    proposal = approved_proposal([e1], b2)
    apply_now(proposal, stub("ok"))

    response = _retry(graphql, token_for, proposal)

    assert error_of(response) == {"code": "CONFLICT", "status": 409}
    assert proposal_status(proposal) == "synced"
    assert apply_messages(proposal) == 1


@pytest.mark.parametrize("status", ["approved", "syncing"])
def test_us15_retry_of_a_proposal_not_sync_failed_409(committed_db, graphql, token_for, status):
    b2, e1 = open_exception("K1")
    proposal = approved_proposal([e1], b2)
    if status == "syncing":
        apply_now(proposal, stub("callback"))

    response = _retry(graphql, token_for, proposal)

    assert error_of(response) == {"code": "CONFLICT", "status": 409}
    assert proposal_status(proposal) == status


def test_us15_c1_clerk_retry_403(sync_failed_p1, graphql, token_for):
    response = _retry(graphql, token_for, sync_failed_p1, user="c1")

    assert error_of(response) == {"code": "FORBIDDEN", "status": 403}
    assert proposal_status(sync_failed_p1) == "sync_failed"
    assert apply_messages(sync_failed_p1) == 1


def test_us15_a1_retry_of_a_t2_proposal_404(committed_db, graphql, token_for):
    b9, e9 = open_exception("K9", tenant_id=C9.tenant_id)
    proposal = pending_proposal([e9], b9, requested_by=C9)
    force_status(proposal, "sync_failed")

    response = _retry(graphql, token_for, proposal)

    assert error_of(response) == {"code": "NOT_FOUND", "status": 404}
    assert proposal_status(proposal) == "sync_failed"
