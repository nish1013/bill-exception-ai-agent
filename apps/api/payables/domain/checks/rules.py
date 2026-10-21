from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from payables.domain.money import Money
from payables.domain.purchase_orders import PurchaseOrder

WHOLE_BILL = "bill"
POSSIBLE_DUPLICATE_WINDOW_DAYS = 7


class Rule(StrEnum):
    DUPLICATE = "duplicate"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    PO_MISMATCH = "po_mismatch"
    MISSING_VAT = "missing_vat"
    MISSING_RECEIPT = "missing_receipt"


@dataclass(frozen=True)
class Finding:
    rule: Rule
    fingerprint: str
    related_bill_id: UUID | None = None

    @classmethod
    def repeat_of(cls, rule: Rule, related_bill_id: UUID) -> "Finding":
        return cls(rule, str(related_bill_id), related_bill_id)

    @classmethod
    def on_whole_bill(cls, rule: Rule) -> "Finding":
        return cls(rule, WHOLE_BILL)

    @property
    def key(self) -> tuple[Rule, str]:
        return (self.rule, self.fingerprint)


@dataclass(frozen=True)
class CheckedBill:
    id: UUID
    supplier_id: UUID
    invoice_number: str
    amount: Money
    issue_date: date
    ingested_at: datetime
    vat_amount_minor: int | None
    has_receipt: bool
    po_number: str | None

    @property
    def ingest_order(self) -> tuple[datetime, str]:
        return (self.ingested_at, str(self.id))


Match = Callable[[CheckedBill, CheckedBill], bool]


def run_rules(
    bill: CheckedBill,
    earlier: Sequence[CheckedBill],
    purchase_order: PurchaseOrder | None,
) -> list[Finding]:
    findings = [
        duplicate(bill, earlier),
        possible_duplicate(bill, earlier),
        po_mismatch(bill, purchase_order),
        missing_vat(bill),
        missing_receipt(bill),
    ]
    return [finding for finding in findings if finding is not None]


def duplicate(bill: CheckedBill, others: Iterable[CheckedBill]) -> Finding | None:
    return _oldest_match(Rule.DUPLICATE, bill, others, _same_invoice_number)


def possible_duplicate(bill: CheckedBill, others: Iterable[CheckedBill]) -> Finding | None:
    return _oldest_match(Rule.POSSIBLE_DUPLICATE, bill, others, _same_amount_near_date)


def po_mismatch(bill: CheckedBill, purchase_order: PurchaseOrder | None) -> Finding | None:
    # A bill with no PO number gets no PO check (D28).
    if bill.po_number is None:
        return None
    if (
        purchase_order is not None
        and purchase_order.supplier_id == bill.supplier_id
        and purchase_order.amount == bill.amount
    ):
        return None
    # The PO number is the fingerprint, so a new PO finds the open exception it repairs (I16).
    return Finding(Rule.PO_MISMATCH, bill.po_number)


def missing_vat(bill: CheckedBill) -> Finding | None:
    # A VAT amount of 0 is a zero-rated bill, not a missing one.
    if bill.vat_amount_minor is not None:
        return None
    return Finding.on_whole_bill(Rule.MISSING_VAT)


def missing_receipt(bill: CheckedBill) -> Finding | None:
    return None if bill.has_receipt else Finding.on_whole_bill(Rule.MISSING_RECEIPT)


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
