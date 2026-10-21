from enum import StrEnum

from payables.domain.checks.rule import Rule
from payables.domain.errors import ValidationError


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def parse(cls, value: str) -> "Severity":
        try:
            return cls(value)
        except ValueError as error:
            raise ValidationError(f"severity {value!r} is not known") from error


# A duplicate or a PO mismatch pays the wrong money. The others are a tax or paper risk (D27).
RULE_SEVERITY: dict[Rule, Severity] = {
    Rule.DUPLICATE: Severity.HIGH,
    Rule.PO_MISMATCH: Severity.HIGH,
    Rule.POSSIBLE_DUPLICATE: Severity.MEDIUM,
    Rule.MISSING_VAT: Severity.MEDIUM,
    Rule.MISSING_RECEIPT: Severity.LOW,
}

WORST_FIRST: tuple[Severity, ...] = (Severity.HIGH, Severity.MEDIUM, Severity.LOW)


def severity_of(rule: Rule) -> Severity:
    return RULE_SEVERITY[rule]


def rules_with(severity: Severity) -> list[Rule]:
    return [rule for rule, rule_severity in RULE_SEVERITY.items() if rule_severity is severity]
