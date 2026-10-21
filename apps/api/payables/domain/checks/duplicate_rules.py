from collections.abc import Callable, Iterable

from payables.domain.checks.checked_bill import CheckedBill
from payables.domain.checks.finding import Finding
from payables.domain.checks.rule import Rule

POSSIBLE_DUPLICATE_WINDOW_DAYS = 7

Match = Callable[[CheckedBill, CheckedBill], bool]


def duplicate(bill: CheckedBill, others: Iterable[CheckedBill]) -> Finding | None:
    return _oldest_match(Rule.DUPLICATE, bill, others, _same_invoice_number)


def possible_duplicate(bill: CheckedBill, others: Iterable[CheckedBill]) -> Finding | None:
    return _oldest_match(Rule.POSSIBLE_DUPLICATE, bill, others, _same_amount_near_date)


def _oldest_match(
    rule: Rule, bill: CheckedBill, others: Iterable[CheckedBill], match: Match
) -> Finding | None:
    # The exception goes on the newer bill only, and refers to the first bill it repeats.
    earlier = [
        other
        for other in others
        if other.supplier_id == bill.supplier_id
        and other.ingest_order < bill.ingest_order
        and match(bill, other)
    ]
    if not earlier:
        return None
    first = min(earlier, key=lambda other: other.ingest_order)
    return Finding.repeat_of(rule, first.id)


def _same_invoice_number(bill: CheckedBill, other: CheckedBill) -> bool:
    return other.invoice_number == bill.invoice_number


def _same_amount_near_date(bill: CheckedBill, other: CheckedBill) -> bool:
    days_apart = abs((other.issue_date - bill.issue_date).days)
    return (
        other.invoice_number != bill.invoice_number
        and other.amount == bill.amount
        and days_apart <= POSSIBLE_DUPLICATE_WINDOW_DAYS
    )
