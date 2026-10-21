import pytest

from payables.domain.checks.exceptions import Severity, rules_with, severity_of
from payables.domain.checks.rules import Rule
from payables.domain.errors import ValidationError


@pytest.mark.parametrize(
    ("rule", "severity"),
    [
        (Rule.DUPLICATE, Severity.HIGH),
        (Rule.PO_MISMATCH, Severity.HIGH),
        (Rule.POSSIBLE_DUPLICATE, Severity.MEDIUM),
        (Rule.MISSING_VAT, Severity.MEDIUM),
        (Rule.MISSING_RECEIPT, Severity.LOW),
    ],
)
def test_d27_each_rule_has_one_severity(rule, severity):
    assert severity_of(rule) is severity


def test_d27_each_rule_in_one_severity_group():
    grouped = [rule for severity in Severity for rule in rules_with(severity)]

    assert sorted(grouped) == sorted(Rule)


@pytest.mark.parametrize("value", ["", "HIGH", "urgent"])
def test_d27_unknown_severity_refused(value):
    with pytest.raises(ValidationError):
        Severity.parse(value)
