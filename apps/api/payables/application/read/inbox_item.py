from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from payables.domain.checks.exception_status import ExceptionStatus
from payables.domain.checks.rule import Rule
from payables.domain.checks.severity import Severity


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
