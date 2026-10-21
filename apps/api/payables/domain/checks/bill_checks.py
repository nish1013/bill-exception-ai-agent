from collections.abc import Sequence

from payables.domain.checks.bill_rules import missing_receipt, missing_vat
from payables.domain.checks.checked_bill import CheckedBill
from payables.domain.checks.duplicate_rules import duplicate, possible_duplicate
from payables.domain.checks.finding import Finding
from payables.domain.checks.po_rules import po_mismatch
from payables.domain.purchase_order import PurchaseOrder


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
