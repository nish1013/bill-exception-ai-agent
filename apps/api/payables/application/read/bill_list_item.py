from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True)
class BillListItem:
    id: UUID
    supplier_name: str
    invoice_number: str
    amount: int
    currency: str
    issue_date: date
    has_receipt: bool
    created_at: datetime
