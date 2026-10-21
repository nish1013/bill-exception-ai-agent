import uuid
from contextlib import ExitStack

import pytest
from django.db import connections, transaction
from django.test.utils import CaptureQueriesContext

from payables.adapters.orm.tenants import tenant_transaction
from tests.check_data import add_bill, add_bulk_bills, check, job_row, start_job
from tests.concurrency import owner_count
from tests.ingest_data import error_of
from tests.tenants import T1, T2

START = """
mutation($ids: [UUID!]!) { startBillCheck(billIds: $ids) { id status billCount } }
"""
VIEWER = "query { viewer { tenantId } }"


@pytest.fixture
def start(graphql, token_for):
    def call(ids: list, user: str = "c1"):
        return graphql(START, token_for(user), {"ids": [str(bill_id) for bill_id in ids]})

    return call


def _started(response) -> dict:
    assert "errors" not in response.json(), response.json()
    return response.json()["data"]["startBillCheck"]


def _statements(call) -> tuple:
    with ExitStack() as stack:
        captured = [stack.enter_context(CaptureQueriesContext(c)) for c in connections.all()]
        response = call()
    return response, sum(len(c.captured_queries) for c in captured)


def test_us5_j1_queued_with_its_messages(committed_db, start):
    bills = [add_bill("K1"), add_bill("K2", invoice_number="INV-002"), add_bill("K3")]

    j1 = _started(start(bills))

    assert (j1["status"], j1["billCount"]) == ("queued", 3)
    assert owner_count("check_job_bill", "job_id = %s AND result = 'pending'", [j1["id"]]) == 3
    assert (
        owner_count(
            "outbox",
            "tenant_id = %s AND command = 'CheckBill' AND payload->>'job_id' = %s "
            "AND sent_at IS NULL",
            [T1, j1["id"]],
        )
        == 3
    )


def test_i14_job_and_messages_roll_back_together(committed_db):
    b1 = add_bill("K1")

    with pytest.raises(RuntimeError):
        with transaction.atomic():
            start_job([b1])
            raise RuntimeError("rollback after the job is written")

    assert owner_count("check_job") == owner_count("outbox") == 0


def test_us5_empty_list_400_no_job(committed_db, start):
    response = start([])

    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert owner_count("check_job") == 0


def test_us5_t2_bill_404_no_job(committed_db, start):
    b1 = add_bill("K1")
    b9 = add_bill("K9", tenant_id=T2)

    response = start([b1, b9])

    assert error_of(response) == {"code": "NOT_FOUND", "status": 404}
    assert owner_count("check_job") == owner_count("outbox") == 0


def test_us5_unknown_bill_404(committed_db, start):
    response = start([add_bill("K1"), uuid.uuid4()])

    assert error_of(response) == {"code": "NOT_FOUND", "status": 404}


def test_us5_approver_403(committed_db, start):
    response = start([add_bill("K1")], user="a1")

    assert error_of(response) == {"code": "FORBIDDEN", "status": 403}
    assert owner_count("check_job") == 0


def test_us5_501_bills_400(committed_db, start):
    add_bill("K1")
    bills = add_bulk_bills(501)

    response = start(bills)

    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert owner_count("check_job") == 0


def test_us5_500_bills_same_statement_count_as_5(committed_db, graphql, token_for, start):
    # The 500 ms target for 500 bills is measured by `make bench` (D38).
    add_bill("K1")
    few, many = add_bulk_bills(5), add_bulk_bills(500, first=6)
    graphql(VIEWER, token_for("c1"))

    few_response, few_statements = _statements(lambda: start(few))
    many_response, many_statements = _statements(lambda: start(many))

    assert _started(few_response)["billCount"] == 5
    assert _started(many_response)["billCount"] == 500
    assert owner_count("outbox") == 505
    assert many_statements == few_statements, f"5 bills: {few_statements}, 500: {many_statements}"


def test_us5_j2_on_bill_of_running_j1(committed_db):
    b1, b2 = add_bill("K1"), add_bill("K2", invoice_number="INV-002")
    j1 = start_job([b1, b2])
    check(j1.id, b2)
    assert job_row(j1.id)[0] == "running"

    j2 = start_job([b1])

    assert job_row(j2.id)[0] == "queued"
    check(j1.id, b1)
    check(j2.id, b1)
    assert job_row(j1.id)[0] == job_row(j2.id)[0] == "completed"


def test_us1_t2_job_bill_rows_hidden_from_t1(committed_db):
    j9 = start_job([add_bill("K9", tenant_id=T2)], tenant_id=T2)

    with tenant_transaction(T1), connections["default"].cursor() as cursor:
        cursor.execute("SELECT count(*) FROM check_job WHERE id = %s", [j9.id])
        assert cursor.fetchone()[0] == 0
