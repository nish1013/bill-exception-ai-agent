from datetime import date

import pytest

from tests.check_data import add_bill, check, exception_id, plant_resolution, seed_po, start_job
from tests.ingest_data import error_of
from tests.tenants import T1, T2

pytestmark = pytest.mark.usefixtures("po_100")

INBOX = """
query($status: String, $severity: String) {
  exceptions(status: $status, severity: $severity) {
    totalCount
    items { billId supplierName invoiceNumber rule severity status relatedBillId }
  }
}
"""


@pytest.fixture
def inbox(graphql, token_for):
    def call(user: str = "c1", **variables):
        return graphql(INBOX, token_for(user), variables)

    return call


def _page(response) -> dict:
    assert "errors" not in response.json(), response.json()
    return response.json()["data"]["exceptions"]


def _listed(response) -> list[dict]:
    return _page(response)["items"]


def _checked(*bill_ids, tenant_id=T1) -> None:
    job = start_job(list(bill_ids), tenant_id)
    for bill_id in bill_ids:
        check(job.id, bill_id, tenant_id)


def _three_open_two_resolved() -> dict[str, object]:
    bills = {
        "b1": add_bill("K1"),
        "b2": add_bill("K2", invoice_number="inv 001"),
        "b3": add_bill("K3", invoice_number="INV-002", issue_date=date(2026, 10, 5)),
        "b4": add_bill("K4", invoice_number="INV-004", amount=4000, po_number="PO-998"),
        "b5": add_bill("K5", invoice_number="INV-005", amount=5000, po_number="PO-999"),
        "b7": add_bill(
            "K7", invoice_number="INV-007", amount=7000, po_number=None, has_receipt=False
        ),
    }
    _checked(*bills.values())
    seed_po("PO-998", amount=4000)
    seed_po("PO-999", amount=5000)
    _checked(bills["b4"], bills["b5"])
    return bills


def test_us8_open_list_high_severity_first(committed_db, inbox):
    bills = _three_open_two_resolved()
    b1, b2, b3, b7 = bills["b1"], bills["b2"], bills["b3"], bills["b7"]

    listed = _listed(inbox(status="open"))

    assert [(row["rule"], row["severity"], row["billId"]) for row in listed] == [
        ("duplicate", "high", str(b2)),
        ("possible_duplicate", "medium", str(b3)),
        ("missing_receipt", "low", str(b7)),
    ]
    assert {row["status"] for row in listed} == {"open"}
    assert listed[0]["relatedBillId"] == str(b1)
    assert (listed[0]["supplierName"], listed[0]["invoiceNumber"]) == ("Fresh Farms Ltd", "inv 001")


def test_us8_t2_open_exceptions_not_listed(committed_db, inbox):
    b91 = add_bill("K91", tenant_id=T2, po_number=None)
    b92 = add_bill("K92", tenant_id=T2, invoice_number="inv 001", po_number=None)
    _checked(b91, b92, tenant_id=T2)

    assert _listed(inbox("c1", status="open")) == []
    assert [row["billId"] for row in _listed(inbox("c9", status="open"))] == [str(b92)]


def test_us8_severity_filter(committed_db, inbox):
    b1 = add_bill("K1")
    b3 = add_bill("K3", invoice_number="INV-002", issue_date=date(2026, 10, 5))
    _checked(b1, b3)

    assert [row["rule"] for row in _listed(inbox(severity="medium"))] == ["possible_duplicate"]
    assert _listed(inbox(severity="high")) == []


def test_us8_resolved_lists_the_two_resolved(committed_db, inbox):
    bills = _three_open_two_resolved()

    listed = _listed(inbox(status="resolved"))

    assert sorted(row["billId"] for row in listed) == sorted([str(bills["b4"]), str(bills["b5"])])
    assert {(row["rule"], row["status"]) for row in listed} == {("po_mismatch", "resolved")}


def test_us8_ignored_lists_only_ignored(committed_db, inbox):
    bills = _three_open_two_resolved()
    plant_resolution(exception_id(bills["b7"], "missing_receipt"), "ignore", "c1", "Agreed")

    listed = _listed(inbox(status="ignored"))

    assert [(row["billId"], row["status"]) for row in listed] == [(str(bills["b7"]), "ignored")]
    assert len(_listed(inbox(status="open"))) == 2
    assert _page(inbox())["totalCount"] == 5


def test_us8_pending_sync_needs_an_approved_proposal(committed_db, inbox):
    _three_open_two_resolved()

    assert _listed(inbox(status="pending_sync")) == []


@pytest.mark.parametrize("variables", [{"status": "closed"}, {"severity": "urgent"}])
def test_us8_unknown_filter_400(committed_db, inbox, variables):
    assert error_of(inbox(**variables)) == {"code": "VALIDATION", "status": 400}
