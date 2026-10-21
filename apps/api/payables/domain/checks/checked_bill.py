from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from payables.domain.money import Money


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
