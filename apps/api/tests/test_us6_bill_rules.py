from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from payables.domain.checks.bill_checks import run_rules
from payables.domain.checks.bill_rules import missing_receipt, missing_vat
from payables.domain.checks.checked_bill import CheckedBill
from payables.domain.checks.finding import Finding
from payables.domain.checks.po_rules import po_mismatch
from payables.domain.checks.rule import Rule
from payables.domain.money import Money
from payables.domain.purchase_order import PurchaseOrder

S1 = UUID(int=1)
S2 = UUID(int=2)

B1 = CheckedBill(
    id=UUID(int=101),
    supplier_id=S1,
    invoice_number="INV001",
    amount=Money(120000, "GBP"),
    issue_date=date(2026, 10, 1),
    ingested_at=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    vat_amount_minor=20000,
    has_receipt=True,
    po_number="PO100",
)
PO_100 = PurchaseOrder(id=UUID(int=900), supplier_id=S1, po_number="PO-100", amount=B1.amount)
MISMATCH = Finding(Rule.PO_MISMATCH, "PO100")


def test_us6_po_100_matches_b1():
    assert po_mismatch(B1, PO_100) is None


@pytest.mark.parametrize(
    "po_changes",
    [
        {"amount": Money(125000, "GBP")},
        {"amount": Money(119999, "GBP")},
        {"amount": Money(120000, "EUR")},
        {"supplier_id": S2},
    ],
)
def test_us6_po_differs_is_mismatch(po_changes):
    assert po_mismatch(B1, replace(PO_100, **po_changes)) == MISMATCH


def test_us6_po_999_missing_is_mismatch():
    b5 = replace(B1, po_number="PO999")

    assert po_mismatch(b5, None) == Finding(Rule.PO_MISMATCH, "PO999")


def test_us6_no_po_number_no_po_check():
    assert po_mismatch(replace(B1, po_number=None), None) is None


@pytest.mark.parametrize(("vat", "found"), [(None, True), (0, False), (1, False), (20000, False)])
def test_us6_missing_vat(vat, found):
    expected = Finding.on_whole_bill(Rule.MISSING_VAT) if found else None

    assert missing_vat(replace(B1, vat_amount_minor=vat)) == expected


@pytest.mark.parametrize(("receipt", "found"), [(False, True), (True, False)])
def test_us6_missing_receipt(receipt, found):
    expected = Finding.on_whole_bill(Rule.MISSING_RECEIPT) if found else None

    assert missing_receipt(replace(B1, has_receipt=receipt)) == expected


def test_us6_run_rules_gives_each_problem_once():
    bad = replace(B1, vat_amount_minor=None, has_receipt=False)

    assert [finding.rule for finding in run_rules(bad, [], None)] == [
        Rule.PO_MISMATCH,
        Rule.MISSING_VAT,
        Rule.MISSING_RECEIPT,
    ]
    assert run_rules(B1, [], PO_100) == []
