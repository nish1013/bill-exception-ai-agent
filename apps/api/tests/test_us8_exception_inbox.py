from datetime import date

import pytest

from tests.check_data import add_bill, check, start_job
from tests.ingest_data import error_of
from tests.tenants import T1, T2

INBOX = """
query($status: String, $severity: String) {
  exceptions(status: $status, severity: $severity) {
    billId supplierName invoiceNumber rule severity status relatedBillId
  }
}
"""


@pytest.fixture
def inbox(graphql, token_for):
    def call(user: str = "c1", **variables):
        return graphql(INBOX, token_for(user), variables)

    return call


def _listed(response) -> list[dict]:
    assert "errors" not in response.json(), response.json()
    return response.json()["data"]["exceptions"]


def _checked(*bill_ids, tenant_id=T1) -> None:
    job = start_job(list(bill_ids), tenant_id)
    for bill_id in bill_ids:
        check(job.id, bill_id, tenant_id)


def test_us8_open_list_high_severity_first(committed_db, inbox):
    b1 = add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    b3 = add_bill("K3", invoice_number="INV-002", issue_date=date(2026, 10, 5))
    _checked(b1, b3, b2)

    listed = _listed(inbox(status="open"))

    assert [(row["rule"], row["severity"], row["billId"]) for row in listed] == [
        ("duplicate", "high", str(b2)),
        ("possible_duplicate", "medium", str(b3)),
    ]
    assert {row["status"] for row in listed} == {"open"}
    assert listed[0]["relatedBillId"] == str(b1)
    assert (listed[0]["supplierName"], listed[0]["invoiceNumber"]) == ("Fresh Farms Ltd", "inv 001")


def test_us8_t2_open_exceptions_not_listed(committed_db, inbox):
    b91 = add_bill("K91", tenant_id=T2)
    b92 = add_bill("K92", tenant_id=T2, invoice_number="inv 001")
    _checked(b91, b92, tenant_id=T2)

    assert _listed(inbox("c1", status="open")) == []
    assert [row["billId"] for row in _listed(inbox("c9", status="open"))] == [str(b92)]


def test_us8_severity_filter(committed_db, inbox):
    b1 = add_bill("K1")
    b3 = add_bill("K3", invoice_number="INV-002", issue_date=date(2026, 10, 5))
    _checked(b1, b3)

    assert [row["rule"] for row in _listed(inbox(severity="medium"))] == ["possible_duplicate"]
    assert _listed(inbox(severity="high")) == []


@pytest.mark.parametrize("status", ["ignored", "resolved", "pending_sync"])
def test_us8_no_resolution_lists_none_as_closed(committed_db, inbox, status):
    b1 = add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    _checked(b1, b2)

    assert _listed(inbox(status=status)) == []


@pytest.mark.parametrize("variables", [{"status": "closed"}, {"severity": "urgent"}])
def test_us8_unknown_filter_400(committed_db, inbox, variables):
    assert error_of(inbox(**variables)) == {"code": "VALIDATION", "status": 400}
