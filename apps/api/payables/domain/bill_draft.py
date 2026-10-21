from dataclasses import dataclass
from datetime import date
from typing import Any

from payables.domain.bill_payload import BillPayload
from payables.domain.document_number import DocumentNumber
from payables.domain.invoice_number import invoice_number
from payables.domain.money import Money
from payables.domain.po_number import optional_po_number
from payables.domain.supplier_identity import SupplierIdentity


@dataclass(frozen=True)
class BillDraft:
    supplier: SupplierIdentity
    invoice_number: DocumentNumber
    amount: Money
    vat_amount: Money | None
    issue_date: date
    po_number: DocumentNumber | None
    has_receipt: bool

    @classmethod
    def parse(cls, payload: BillPayload) -> "BillDraft":
        amount = Money(payload.amount, payload.currency)
        return cls(
            supplier=SupplierIdentity.parse(payload.supplier_name, payload.supplier_vat_number),
            invoice_number=invoice_number(payload.invoice_number),
            amount=amount,
            vat_amount=_vat_amount(payload.vat_amount, amount.currency),
            issue_date=payload.issue_date,
            po_number=optional_po_number(payload.po_number),
            has_receipt=payload.has_receipt,
        )


def _vat_amount(value: Any, currency: str) -> Money | None:
    return None if value is None else Money(value, currency)
