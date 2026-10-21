import pytest

from tests.check_data import add_bill, check, start_job
from tests.ingest_data import error_of
from tests.tenants import T2

CHECK_JOB = "query($id: UUID!) { checkJob(id: $id) { id status billCount okCount failedCount } }"


@pytest.fixture
def check_job(graphql, token_for):
    def call(job_id, user: str = "c1"):
        return graphql(CHECK_JOB, token_for(user), {"id": str(job_id)})

    return call


def _job(response) -> dict:
    assert "errors" not in response.json(), response.json()
    return response.json()["data"]["checkJob"]


def test_us5_poll_shows_queued_then_completed(committed_db, check_job):
    b1, b2 = add_bill("K1"), add_bill("K2", invoice_number="INV-002")
    j1 = start_job([b1, b2])

    assert _job(check_job(j1.id))["status"] == "queued"

    check(j1.id, b1)
    assert (_job(check_job(j1.id))["status"], _job(check_job(j1.id))["okCount"]) == ("running", 1)

    check(j1.id, b2)
    assert _job(check_job(j1.id)) == {
        "id": str(j1.id),
        "status": "completed",
        "billCount": 2,
        "okCount": 2,
        "failedCount": 0,
    }


def test_us5_t2_job_not_found_for_t1(committed_db, check_job):
    j9 = start_job([add_bill("K9", tenant_id=T2)], T2)

    assert error_of(check_job(j9.id)) == {"code": "NOT_FOUND", "status": 404}
    assert _job(check_job(j9.id, "c9"))["status"] == "queued"
