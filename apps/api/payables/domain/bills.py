import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from uuid import UUID

from payables.domain.errors import ValidationError
from payables.domain.money import Money
from payables.domain.purchase_orders import optional_po_number
from payables.domain.suppliers import SupplierIdentity
from payables.domain.text import DocumentNumber

MAX_LENGTH = 255


@dataclass(frozen=True)
class BillPayload:
    supplier_name: str
    supplier_vat_number: str | None
    invoice_number: str
    amount: Any
    currency: str
    vat_amount: Any
    issue_date: date
    po_number: str | None
    has_receipt: bool

    def digest(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()


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


@dataclass(frozen=True)
class StoredBill:
    id: UUID
    supplier_id: UUID
    payload_hash: str


@dataclass(frozen=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.value) <= MAX_LENGTH or not self.value.isprintable():
            raise ValidationError(f"idempotency key must be 1 to {MAX_LENGTH} printable characters")


def invoice_number(raw: str) -> DocumentNumber:
    return DocumentNumber.parse(raw, "invoice number")


def _vat_amount(value: Any, currency: str) -> Money | None:
    return None if value is None else Money(value, currency)
