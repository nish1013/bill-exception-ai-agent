from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from payables.domain.checks.exceptions import ExceptionStatus, Severity
from payables.domain.checks.rules import Rule


@dataclass(frozen=True)
class InboxItem:
    id: UUID
    bill_id: UUID
    supplier_name: str
    invoice_number: str
    rule: Rule
    severity: Severity
    status: ExceptionStatus
    related_bill_id: UUID | None
    created_at: datetime
    resolved_by: str | None
    reason: str | None
