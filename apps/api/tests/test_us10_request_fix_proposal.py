import uuid

import pytest
import redis

from payables.adapters.rate_limit import RedisProposalRateLimiter
from tests.check_data import plant_resolution
from tests.concurrency import owner_count
from tests.ingest_data import error_of
from tests.proposal_data import open_exception, request_now, seed_slots, slots_today
from tests.tenants import T2

pytestmark = pytest.mark.usefixtures("po_100", "fresh_rate_limit")

REQUEST = """
mutation($ids: [UUID!]!) {
  requestFixProposal(exceptionIds: $ids) {
    id status quotaSlot requestedBy failedReason
    exceptions { id rule invoiceNumber }
    actions { kind }
  }
}
"""
PROPOSALS = "query($status: String) { proposals(status: $status) { totalCount items { id } } }"
PROPOSAL = "query($id: UUID!) { proposal(id: $id) { id status } }"


@pytest.fixture
def request_proposal(graphql, token_for):
    def call(*exception_ids, user: str = "c1"):
        ids = [str(e) for e in exception_ids]
        return graphql(REQUEST, token_for(user), {"ids": ids})

    return call


def test_us10_p1_drafting_and_t1_used_4_of_50(committed_db, request_proposal):
    _, e1 = open_exception("K1")
    _, e4 = open_exception("K4")
    seed_slots(3)

    response = request_proposal(e1, e4)

    p1 = response.json()["data"]["requestFixProposal"]
    assert (p1["status"], p1["quotaSlot"], p1["requestedBy"], p1["actions"]) == (
        "drafting",
        4,
        "c1",
        [],
    )
    assert sorted(e["id"] for e in p1["exceptions"]) == sorted([str(e1), str(e4)])
    assert slots_today() == [1, 2, 3, 4]
    assert (
        owner_count(
            "outbox", "command = 'DraftFixProposal' AND payload->>'proposal_id' = %s", [p1["id"]]
        )
        == 1
    )


def test_us10_50_of_50_used_429_no_proposal(committed_db, request_proposal):
    _, e1 = open_exception("K1")
    seed_slots(50)

    response = request_proposal(e1)

    assert response.status_code == 429
    assert error_of(response) == {"code": "RATE_LIMITED", "status": 429}
    assert slots_today() == list(range(1, 51))
    assert owner_count("outbox", "command = 'DraftFixProposal'") == 0


def test_us10_yesterday_slots_do_not_count_today(committed_db, request_proposal):
    _, e1 = open_exception("K1")
    seed_slots(50, days_from_today=-1)

    response = request_proposal(e1)

    assert response.json()["data"]["requestFixProposal"]["quotaSlot"] == 1


def test_us10_5_requests_in_a_minute_then_429_no_proposal(committed_db, request_proposal):
    _, e1 = open_exception("K1")
    for _ in range(5):
        assert request_proposal(e1).json()["data"]["requestFixProposal"]["status"] == "drafting"

    response = request_proposal(e1)

    assert response.status_code == 429
    assert error_of(response) == {"code": "RATE_LIMITED", "status": 429}
    assert slots_today() == [1, 2, 3, 4, 5]


@pytest.mark.parametrize(
    ("kind", "actor", "reason"),
    [("system", "system", None), ("ignore", "c1", "Agreed with supplier")],
)
def test_us10_e5_not_open_400_no_proposal(committed_db, request_proposal, kind, actor, reason):
    _, e5 = open_exception("K5")
    plant_resolution(e5, kind, actor, reason)

    response = request_proposal(e5)

    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert slots_today() == []


def test_us10_t2_exception_e9_not_found(committed_db, request_proposal):
    _, e9 = open_exception("K9", tenant_id=T2)

    response = request_proposal(e9)

    assert error_of(response) == {"code": "NOT_FOUND", "status": 404}
    assert slots_today() == [] and slots_today(T2) == []


def test_us10_one_known_one_unknown_not_found(committed_db, request_proposal):
    _, e1 = open_exception("K1")

    response = request_proposal(e1, uuid.uuid4())

    assert error_of(response) == {"code": "NOT_FOUND", "status": 404}
    assert slots_today() == []


@pytest.mark.parametrize("count", [0, 8])
def test_us10_empty_or_over_7_exceptions_400(committed_db, request_proposal, count):
    exceptions = [open_exception(f"K{n}")[1] for n in range(count)]

    response = request_proposal(*exceptions)

    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert slots_today() == []


def test_us10_same_exception_twice_counts_once(committed_db, request_proposal):
    _, e1 = open_exception("K1")

    response = request_proposal(e1, e1)

    assert len(response.json()["data"]["requestFixProposal"]["exceptions"]) == 1


def test_us10_approver_403(committed_db, request_proposal):
    _, e1 = open_exception("K1")

    response = request_proposal(e1, user="a1")

    assert error_of(response) == {"code": "FORBIDDEN", "status": 403}
    assert slots_today() == []


def test_us10_t2_token_reads_no_t1_proposal(committed_db, graphql, token_for):
    _, e1 = open_exception("K1")
    p1 = request_now([e1])

    t2_list = graphql(PROPOSALS, token_for("c9")).json()["data"]["proposals"]
    t2_read = graphql(PROPOSAL, token_for("c9"), {"id": str(p1)})
    t1_read = graphql(PROPOSAL, token_for("c1"), {"id": str(p1)})

    assert t2_list == {"totalCount": 0, "items": []}
    assert error_of(t2_read) == {"code": "NOT_FOUND", "status": 404}
    assert t1_read.json()["data"]["proposal"] == {"id": str(p1), "status": "drafting"}


def test_us10_proposals_filter_by_status(committed_db, graphql, token_for):
    _, e1 = open_exception("K1")
    p1 = request_now([e1])

    def ids(status):
        data = graphql(PROPOSALS, token_for("a1"), {"status": status}).json()["data"]
        return [item["id"] for item in data["proposals"]["items"]]

    assert ids("drafting") == [str(p1)]
    assert ids("pending") == []
    assert error_of(graphql(PROPOSALS, token_for("c1"), {"status": "nope"})) == {
        "code": "VALIDATION",
        "status": 400,
    }


def test_us10_redis_down_rate_limit_allows():
    limiter = RedisProposalRateLimiter(redis.Redis(host="redis", port=1, socket_timeout=0.2))

    assert all(limiter.allow(T2) for _ in range(6))
