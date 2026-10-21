import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


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
