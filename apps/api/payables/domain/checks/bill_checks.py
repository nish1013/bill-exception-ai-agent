from collections.abc import Sequence

from payables.domain.checks.checked_bill import CheckedBill
from payables.domain.checks.duplicate_rules import duplicate, possible_duplicate
from payables.domain.checks.finding import Finding

RULES = (duplicate, possible_duplicate)


def run_rules(bill: CheckedBill, others: Sequence[CheckedBill]) -> list[Finding]:
    return [finding for rule in RULES if (finding := rule(bill, others)) is not None]
