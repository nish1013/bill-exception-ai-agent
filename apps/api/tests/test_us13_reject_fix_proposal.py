import pytest

from payables.domain.access import Principal, Role
from tests.approval_data import A1, approve, now, pending_proposal, proposal_state
from tests.ingest_data import error_of
from tests.proposal_data import audit_of, open_exception
from tests.tenants import T1

pytestmark = pytest.mark.usefixtures("po_100")

REJECT = """
mutation($id: UUID!, $reason: String!) {
  rejectFixProposal(proposalId: $id, reason: $reason) { id status rejectReason approvedBy }
}
"""
EXCEPTIONS = "{ exceptions { items { id status } } }"


@pytest.fixture
def p1(committed_db):
    b2, e1 = open_exception("K1")
    _, e4 = open_exception("K4")
    return pending_proposal([e1, e4], b2), e1, e4


def _reject(graphql, token_for, proposal_id, reason="Wrong supplier", user="a1"):
    return graphql(REJECT, token_for(user), {"id": str(proposal_id), "reason": reason})


def test_us13_a1_rejects_p1_exceptions_stay_open_audit_reason(p1, graphql, token_for):
    proposal, e1, e4 = p1

    response = _reject(graphql, token_for, proposal, "  Wrong supplier ")

    rejected = response.json()["data"]["rejectFixProposal"]
    assert (rejected["status"], rejected["rejectReason"]) == ("rejected", "Wrong supplier")
    assert proposal_state(proposal) == ("rejected", None, "Wrong supplier")
    assert audit_of(proposal) == [("proposal_rejected", "a1", {"reason": "Wrong supplier"})]
    items = graphql(EXCEPTIONS, token_for("c1")).json()["data"]["exceptions"]["items"]
    statuses = {item["id"]: item["status"] for item in items}
    assert (statuses[str(e1)], statuses[str(e4)]) == ("open", "open")


def test_us13_approved_p1_reject_409_stays_approved(p1, graphql, token_for):
    proposal, _, _ = p1
    now(approve(A1, proposal))

    response = _reject(graphql, token_for, proposal, user="a2")

    assert error_of(response) == {"code": "CONFLICT", "status": 409}
    assert proposal_state(proposal) == ("approved", "a1", None)
    assert [kind for kind, _, _ in audit_of(proposal)] == ["proposal_approved"]


@pytest.mark.parametrize("reason", ["", "   ", "x" * 1001])
def test_us13_reject_without_a_valid_reason_400(p1, graphql, token_for, reason):
    proposal, _, _ = p1

    response = _reject(graphql, token_for, proposal, reason)

    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert proposal_state(proposal) == ("pending", None, None)


def test_us13_clerk_rejects_403(p1, graphql, token_for):
    proposal, _, _ = p1

    response = _reject(graphql, token_for, proposal, user="c1")

    assert error_of(response) == {"code": "FORBIDDEN", "status": 403}


def test_us13_requester_can_reject_own_proposal(committed_db, graphql, token_for):
    b2, e1 = open_exception("K1")
    proposal = pending_proposal([e1], b2, requested_by=Principal(T1, Role.CLERK, "a1"))

    response = _reject(graphql, token_for, proposal)

    assert response.json()["data"]["rejectFixProposal"]["status"] == "rejected"


def test_us13_unknown_proposal_404(committed_db, graphql, token_for):
    response = _reject(graphql, token_for, "00000000-0000-4000-8000-000000000000")

    assert error_of(response) == {"code": "NOT_FOUND", "status": 404}
