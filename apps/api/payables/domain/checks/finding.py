from dataclasses import dataclass
from uuid import UUID

from payables.domain.checks.rule import Rule

WHOLE_BILL = "bill"


@dataclass(frozen=True)
class Finding:
    rule: Rule
    fingerprint: str
    related_bill_id: UUID | None = None

    @classmethod
    def repeat_of(cls, rule: Rule, related_bill_id: UUID) -> "Finding":
        return cls(rule, str(related_bill_id), related_bill_id)

    @classmethod
    def on_whole_bill(cls, rule: Rule) -> "Finding":
        return cls(rule, WHOLE_BILL)

    @property
    def key(self) -> tuple[Rule, str]:
        return (self.rule, self.fingerprint)
