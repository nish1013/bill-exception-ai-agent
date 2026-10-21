from payables.domain.checks.checked_bill import CheckedBill
from payables.domain.checks.finding import Finding
from payables.domain.checks.rule import Rule


def missing_vat(bill: CheckedBill) -> Finding | None:
    # A VAT amount of 0 is a zero-rated bill, not a missing one.
    if bill.vat_amount_minor is not None:
        return None
    return Finding.on_whole_bill(Rule.MISSING_VAT)


def missing_receipt(bill: CheckedBill) -> Finding | None:
    return None if bill.has_receipt else Finding.on_whole_bill(Rule.MISSING_RECEIPT)
