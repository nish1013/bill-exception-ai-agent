import time
import uuid

import pytest
from django.db import connections, transaction

from payables.adapters.orm.tenancy import tenant_transaction
from tests.check_data import add_bill, check, job_row, start_job
from tests.concurrency import owner_count
from tests.ingest_data import error_of
from tests.tenants import T1, T2

START = """
mutation($ids: [UUID!]!) { startBillCheck(billIds: $ids) { id status billCount } }
"""
VIEWER = "query { viewer { tenantId } }"
BULK_BILLS = """
INSERT INTO bill (id, tenant_id, supplier_id, invoice_number, invoice_number_norm, amount_minor,
                  currency, issue_date, has_receipt, idempotency_key, payload_hash, created_at)
SELECT gen_random_uuid(), %s, %s, 'INV-' || n, 'INV' || n, 100 + n, 'GBP', '2026-10-01', true,
       'bulk-' || n, 'h', now()
FROM generate_series(1, %s) AS n
RETURNING id
"""


@pytest.fixture
def start(graphql, token_for):
    def call(ids: list, user: str = "c1"):
        return graphql(START, token_for(user), {"ids": [str(bill_id) for bill_id in ids]})

    return call


def _started(response) -> dict:
    assert "errors" not in response.json(), response.json()
    return response.json()["data"]["startBillCheck"]


def _bulk_bills(count: int) -> list:
    with connections["owner"].cursor() as cursor:
        cursor.execute("SELECT supplier_id FROM bill WHERE tenant_id = %s LIMIT 1", [T1])
        supplier_id = cursor.fetchone()[0]
        cursor.execute(BULK_BILLS, [T1, supplier_id, count])
        return [row[0] for row in cursor.fetchall()]


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
    bills = _bulk_bills(501)

    response = start(bills)

    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert owner_count("check_job") == 0


def test_us5_500_bills_under_500_ms(committed_db, graphql, token_for, start):
    add_bill("K1")
    bills = _bulk_bills(500)
    graphql(VIEWER, token_for("c1"))

    began = time.perf_counter()
    response = start(bills)
    elapsed = time.perf_counter() - began

    assert _started(response)["billCount"] == 500
    assert owner_count("outbox") == 500
    assert elapsed < 0.5, f"startBillCheck took {elapsed * 1000:.0f} ms"


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
