from payables.domain.checks.checked_bill import CheckedBill
from payables.domain.checks.finding import Finding
from payables.domain.checks.rule import Rule
from payables.domain.purchase_order import PurchaseOrder


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
