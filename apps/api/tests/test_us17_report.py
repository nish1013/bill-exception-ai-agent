from typing import Any
from uuid import UUID

import pytest

from tests.check_data import add_bill, check, exception_id, plant_resolution, start_job
from tests.sync_data import approved_proposal, force_status
from tests.tenants import T1, T2

pytestmark = pytest.mark.usefixtures("po_100")

REPORT = """
query {
  report {
    openExceptions
    moneyAtRisk { currency amount }
  }
}
"""

TWO_OPEN: dict[str, Any] = {"vat_amount": None, "has_receipt": False}
ONE_OPEN: dict[str, Any] = {"has_receipt": False}


@pytest.fixture
def report(graphql, token_for):
    def call(user: str = "c1") -> dict:
        body = graphql(REPORT, token_for(user)).json()
        assert "errors" not in body, body
        return body["data"]["report"]

    return call


def _checked(key: str, open_rules: dict[str, Any], tenant_id: UUID = T1, **changes: Any) -> UUID:
    fields = {"po_number": None, "invoice_number": f"INV-{key}", **open_rules, **changes}
    bill_id = add_bill(key, tenant_id, **fields)
    check(start_job([bill_id], tenant_id).id, bill_id, tenant_id)
    return bill_id


def test_us17_open_and_pending_sync_money_per_currency(committed_db, report):
    _checked("B2", TWO_OPEN)
    b8 = _checked("B8", ONE_OPEN, amount=5000, currency="EUR", vat_amount=0)
    approved_proposal([exception_id(b8, "missing_receipt")], b8)

    assert report() == {
        "openExceptions": 2,
        "moneyAtRisk": [{"currency": "EUR", "amount": 5000}, {"currency": "GBP", "amount": 120000}],
    }


def test_us17_bill_with_two_open_exceptions_counts_once(committed_db, report):
    _checked("B2", TWO_OPEN)

    assert report() == {
        "openExceptions": 2,
        "moneyAtRisk": [{"currency": "GBP", "amount": 120000}],
    }


def test_us17_bills_of_one_currency_add_up(committed_db, report):
    _checked("B2", TWO_OPEN)
    _checked("B3", ONE_OPEN, amount=30000)

    assert report()["moneyAtRisk"] == [{"currency": "GBP", "amount": 150000}]


@pytest.mark.parametrize(
    ("kind", "actor", "reason"), [("ignore", "c1", "Agreed"), ("system", "system", None)]
)
def test_us17_ignored_or_resolved_adds_nothing(committed_db, report, kind, actor, reason):
    b6 = _checked("B6", ONE_OPEN)
    plant_resolution(exception_id(b6, "missing_receipt"), kind, actor, reason)

    assert report() == {"openExceptions": 0, "moneyAtRisk": []}


@pytest.mark.parametrize(
    ("status", "at_risk"),
    [("approved", True), ("syncing", True), ("sync_failed", True), ("synced", False)],
)
def test_us17_proposal_resolution_at_risk_until_synced(committed_db, report, status, at_risk):
    b8 = _checked("B8", ONE_OPEN, amount=5000, currency="EUR")
    force_status(approved_proposal([exception_id(b8, "missing_receipt")], b8), status)

    expected = [{"currency": "EUR", "amount": 5000}] if at_risk else []
    assert report() == {"openExceptions": 0, "moneyAtRisk": expected}


def test_us17_t2_numbers_not_in_report(committed_db, report):
    _checked("B91", TWO_OPEN, tenant_id=T2)

    assert report("c1") == {"openExceptions": 0, "moneyAtRisk": []}
    assert report("c9") == {
        "openExceptions": 2,
        "moneyAtRisk": [{"currency": "GBP", "amount": 120000}],
    }
