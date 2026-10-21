from dataclasses import dataclass
from uuid import UUID

from payables.domain.checks.rule import Rule


@dataclass(frozen=True)
class Finding:
    rule: Rule
    related_bill_id: UUID

    @property
    def fingerprint(self) -> str:
        return str(self.related_bill_id)
