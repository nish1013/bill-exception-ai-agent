import pytest
from django.db import connections

from config.celery import app
from payables.adapters.broker import APPLY, CeleryPublisher
from payables.adapters.outbox import OutboxRelay
from payables.domain.access import Principal, Role
from tests.approval_data import (
    A1,
    apply_messages,
    approve,
    now,
    pending_proposal,
    proposal_resolutions,
    proposal_state,
)
from tests.broker import queue_stats
from tests.check_data import C9
from tests.ingest_data import error_of
from tests.proposal_data import audit_of, open_exception
from tests.tenants import T1

pytestmark = pytest.mark.usefixtures("po_100")

APPROVE = """
mutation($id: UUID!) {
  approveFixProposal(proposalId: $id) { id status approvedBy approvedAt rejectReason }
}
"""
IGNORE = """
mutation($id: UUID!) { ignoreException(exceptionId: $id, reason: "Paid by card") { id } }
"""
EXCEPTIONS = "query($status: String) { exceptions(status: $status) { items { id status } } }"


@pytest.fixture
def p1(committed_db):
    b2, e1 = open_exception("K1")
    _, e4 = open_exception("K4")
    return pending_proposal([e1, e4], b2), e1, e4


def _approve(graphql, token_for, proposal_id, user="a1"):
    return graphql(APPROVE, token_for(user), {"id": str(proposal_id)})


def _statuses(graphql, token_for, status=None):
    response = graphql(EXCEPTIONS, token_for("c1"), {"status": status})
    return {item["id"]: item["status"] for item in response.json()["data"]["exceptions"]["items"]}


def test_us12_a1_approves_p1_audit_pending_sync_apply_enqueued(p1, graphql, token_for):
    proposal, e1, e4 = p1

    response = _approve(graphql, token_for, proposal)

    approved = response.json()["data"]["approveFixProposal"]
    assert (approved["status"], approved["approvedBy"]) == ("approved", "a1")
    assert approved["approvedAt"] is not None
    assert proposal_state(proposal) == ("approved", "a1", None)
    assert [(kind, actor, payload) for kind, actor, payload in audit_of(proposal)] == [
        (
            "proposal_approved",
            "a1",
            {"requested_by": "c1", "exception_ids": sorted([str(e1), str(e4)])},
        )
    ]
    assert proposal_resolutions(e1) == [("proposal", "a1", proposal)]
    assert proposal_resolutions(e4) == [("proposal", "a1", proposal)]
    statuses = _statuses(graphql, token_for)
    assert (statuses[str(e1)], statuses[str(e4)]) == ("pending_sync", "pending_sync")
    assert apply_messages(proposal) == 1


def test_us12_pending_sync_filter_and_synced_proposal_resolves(p1, graphql, token_for):
    proposal, e1, _ = p1
    _approve(graphql, token_for, proposal)

    assert str(e1) in _statuses(graphql, token_for, "pending_sync")
    assert str(e1) not in _statuses(graphql, token_for, "open")
    with connections["owner"].cursor() as cursor:
        cursor.execute("UPDATE proposal SET status = 'synced' WHERE id = %s", [proposal])
    assert _statuses(graphql, token_for, "resolved")[str(e1)] == "resolved"
    assert str(e1) not in _statuses(graphql, token_for, "pending_sync")


def test_us12_requested_by_a1_a1_approves_403_stays_pending(committed_db, graphql, token_for):
    b2, e1 = open_exception("K1")
    proposal = pending_proposal([e1], b2, requested_by=Principal(T1, Role.CLERK, "a1"))

    response = _approve(graphql, token_for, proposal)

    assert error_of(response) == {"code": "FORBIDDEN", "status": 403}
    assert proposal_state(proposal) == ("pending", None, None)
    assert proposal_resolutions(e1) == []
    assert audit_of(proposal) == []
    assert apply_messages(proposal) == 0


def test_us12_c1_clerk_approves_403(committed_db, graphql, token_for):
    b2, e1 = open_exception("K1")
    # Another clerk requested P1, so only the role refuses C1.
    proposal = pending_proposal([e1], b2, requested_by=Principal(T1, Role.CLERK, "c2"))

    response = _approve(graphql, token_for, proposal, user="c1")

    assert error_of(response) == {"code": "FORBIDDEN", "status": 403}
    assert proposal_state(proposal) == ("pending", None, None)


def test_us12_c1_ignored_e4_after_draft_409_p1_stale(p1, graphql, token_for):
    proposal, e1, e4 = p1
    graphql(IGNORE, token_for("c1"), {"id": str(e4)})

    response = _approve(graphql, token_for, proposal)

    assert error_of(response) == {"code": "CONFLICT", "status": 409}
    assert proposal_state(proposal) == ("stale", None, None)
    assert proposal_resolutions(e1) == []
    assert [row[0] for row in proposal_resolutions(e4)] == ["ignore"]
    assert [(kind, actor) for kind, actor, _ in audit_of(proposal)] == [("proposal_stale", "a1")]
    assert apply_messages(proposal) == 0
    assert _statuses(graphql, token_for)[str(e1)] == "open"


def test_us12_stale_p1_approved_again_409_stays_stale(p1, graphql, token_for):
    proposal, _, e4 = p1
    graphql(IGNORE, token_for("c1"), {"id": str(e4)})
    _approve(graphql, token_for, proposal)

    response = _approve(graphql, token_for, proposal, user="a2")

    assert error_of(response) == {"code": "CONFLICT", "status": 409}
    assert proposal_state(proposal) == ("stale", None, None)
    assert [kind for kind, _, _ in audit_of(proposal)] == ["proposal_stale"]


def test_us12_t2_proposal_not_found_for_a1(committed_db, graphql, token_for):
    b9, e9 = open_exception("K9", tenant_id=C9.tenant_id)
    proposal = pending_proposal([e9], b9, requested_by=C9)

    response = _approve(graphql, token_for, proposal)

    assert error_of(response) == {"code": "NOT_FOUND", "status": 404}
    assert proposal_state(proposal) == ("pending", None, None)


@pytest.mark.usefixtures("fresh_rate_limit")
def test_us12_approved_exception_cannot_join_a_new_proposal(p1, graphql, token_for):
    proposal, e1, _ = p1
    _approve(graphql, token_for, proposal)
    request = "mutation($ids: [UUID!]!) { requestFixProposal(exceptionIds: $ids) { id } }"

    response = graphql(request, token_for("c1"), {"ids": [str(e1)]})

    assert error_of(response) == {"code": "VALIDATION", "status": 400}


def test_us12_relay_puts_apply_message_in_the_apply_queue(p1, queues):
    proposal, _, _ = p1
    now(approve(A1, proposal))

    assert OutboxRelay(CeleryPublisher(app)).publish_pending() >= 1

    assert queue_stats(queues, APPLY).ready == 1
