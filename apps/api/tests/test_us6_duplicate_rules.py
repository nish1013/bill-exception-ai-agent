from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from payables.domain.checks.bill_checks import run_rules
from payables.domain.checks.checked_bill import CheckedBill
from payables.domain.checks.duplicate_rules import duplicate, possible_duplicate
from payables.domain.checks.finding import Finding
from payables.domain.checks.rule import Rule
from payables.domain.money import Money

S1 = UUID(int=1)
S2 = UUID(int=2)
T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

B1 = CheckedBill(
    id=UUID(int=101),
    supplier_id=S1,
    invoice_number="INV001",
    amount=Money(120000, "GBP"),
    issue_date=date(2026, 10, 1),
    ingested_at=T0,
)


def later(bill: CheckedBill, minutes: int, **changes) -> CheckedBill:
    return replace(
        bill,
        id=UUID(int=bill.id.int + minutes),
        ingested_at=T0 + timedelta(minutes=minutes),
        **changes,
    )


def test_us6_newer_bill_same_number_is_duplicate():
    b2 = later(B1, 1)

    assert duplicate(b2, [B1]) == Finding(Rule.DUPLICATE, B1.id)
    assert duplicate(B1, [b2]) is None


def test_us6_duplicate_refers_to_first_bill():
    b2, b3 = later(B1, 1), later(B1, 2)

    assert duplicate(b3, [b2, B1]) == Finding(Rule.DUPLICATE, B1.id)


def test_us6_same_ingest_time_orders_by_id():
    twin = replace(B1, id=UUID(int=102))

    assert duplicate(twin, [B1]) == Finding(Rule.DUPLICATE, B1.id)
    assert duplicate(B1, [twin]) is None


def test_us6_other_supplier_is_no_duplicate():
    assert duplicate(later(B1, 1, supplier_id=S2), [B1]) is None


@pytest.mark.parametrize(
    ("issued", "found"),
    [
        (date(2026, 10, 5), True),
        (date(2026, 10, 8), True),
        (date(2026, 10, 9), False),
        (date(2026, 9, 24), True),
        (date(2026, 9, 23), False),
    ],
)
def test_us6_possible_duplicate_7_day_window(issued, found):
    b3 = later(B1, 1, invoice_number="INV002", issue_date=issued)

    expected = Finding(Rule.POSSIBLE_DUPLICATE, B1.id) if found else None
    assert possible_duplicate(b3, [B1]) == expected


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": Money(120001, "GBP")},
        {"amount": Money(120000, "EUR")},
        {"invoice_number": "INV001"},
        {"supplier_id": S2},
    ],
)
def test_us6_no_possible_duplicate(changes):
    b3 = later(B1, 1, **({"invoice_number": "INV002"} | changes))

    assert possible_duplicate(b3, [B1]) is None


def test_us6_run_rules_gives_each_rule_once():
    b2 = later(B1, 1)
    b3 = later(B1, 2, invoice_number="INV002")

    assert run_rules(b3, [B1, b2]) == [Finding(Rule.POSSIBLE_DUPLICATE, B1.id)]
    assert run_rules(later(B1, 3), [B1, b2, b3]) == [
        Finding(Rule.DUPLICATE, B1.id),
        Finding(Rule.POSSIBLE_DUPLICATE, b3.id),
    ]
