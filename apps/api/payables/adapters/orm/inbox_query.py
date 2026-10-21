from uuid import UUID

from django.db.models import Case, IntegerField, Value, When

from payables.adapters.orm.exception import ExceptionRow
from payables.application.read.inbox_item import InboxItem
from payables.domain.checks.exception_status import ExceptionStatus
from payables.domain.checks.rule import Rule
from payables.domain.checks.severity import WORST_FIRST, Severity, rules_with, severity_of

LIST_LIMIT = 500


class InboxOrmQuery:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def worst_first(self, severity: Severity | None) -> list[InboxItem]:
        rows = ExceptionRow.objects.filter(tenant_id=self._tenant_id)
        if severity is not None:
            rows = rows.filter(rule__in=[rule.value for rule in rules_with(severity)])
        rows = (
            rows.annotate(severity_rank=_severity_rank())
            .order_by("severity_rank", "-created_at", "-id")
            .values(
                "id",
                "bill_id",
                "bill__supplier__name",
                "bill__invoice_number",
                "rule",
                "related_bill_id",
                "created_at",
            )[:LIST_LIMIT]
        )
        return [_item(row) for row in rows]


def _severity_rank() -> Case:
    return Case(
        *[
            When(rule__in=[rule.value for rule in rules_with(severity)], then=Value(rank))
            for rank, severity in enumerate(WORST_FIRST)
        ],
        default=Value(len(WORST_FIRST)),
        output_field=IntegerField(),
    )


def _item(row: dict) -> InboxItem:
    rule = Rule(row["rule"])
    return InboxItem(
        id=row["id"],
        bill_id=row["bill_id"],
        supplier_name=row["bill__supplier__name"],
        invoice_number=row["bill__invoice_number"],
        rule=rule,
        severity=severity_of(rule),
        status=ExceptionStatus.OPEN,
        related_bill_id=row["related_bill_id"],
        created_at=row["created_at"],
    )
