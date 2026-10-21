from uuid import UUID

from django.db.models import Case, IntegerField, Q, QuerySet, Value, When

from payables.adapters.orm.exception import ExceptionRow
from payables.application.read.inbox_filter import InboxFilter
from payables.application.read.inbox_item import InboxItem
from payables.application.read.list_page import ListPage
from payables.domain.checks.exception_status import ExceptionStatus, kinds_with, status_of
from payables.domain.checks.resolution_kind import ResolutionKind
from payables.domain.checks.rule import Rule
from payables.domain.checks.severity import WORST_FIRST, rules_with, severity_of

LIST_LIMIT = 500

FIELDS = (
    "id",
    "bill_id",
    "bill__supplier__name",
    "bill__invoice_number",
    "rule",
    "related_bill_id",
    "created_at",
    "resolution__kind",
    "resolution__actor",
    "resolution__reason",
)


class InboxOrmQuery:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def worst_first(self, filters: InboxFilter) -> ListPage[InboxItem]:
        rows = self._rows()
        if filters.status is not None:
            rows = rows.filter(_with_status(filters.status))
        if filters.severity is not None:
            rows = rows.filter(rule__in=[rule.value for rule in rules_with(filters.severity)])
        listed = (
            rows.annotate(severity_rank=_severity_rank())
            .order_by("severity_rank", "-created_at", "-id")
            .values(*FIELDS)[:LIST_LIMIT]
        )
        return ListPage(items=[_item(row) for row in listed], total_count=rows.count())

    def find(self, exception_id: UUID) -> InboxItem | None:
        row = self._rows().filter(id=exception_id).values(*FIELDS).first()
        return None if row is None else _item(row)

    def _rows(self) -> QuerySet[ExceptionRow]:
        return ExceptionRow.objects.filter(tenant_id=self._tenant_id)


def _with_status(status: ExceptionStatus) -> Q:
    if status is ExceptionStatus.OPEN:
        return Q(resolution__isnull=True)
    return Q(resolution__kind__in=[kind.value for kind in kinds_with(status)])


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
    kind = row["resolution__kind"]
    return InboxItem(
        id=row["id"],
        bill_id=row["bill_id"],
        supplier_name=row["bill__supplier__name"],
        invoice_number=row["bill__invoice_number"],
        rule=rule,
        severity=severity_of(rule),
        status=status_of(None if kind is None else ResolutionKind(kind)),
        related_bill_id=row["related_bill_id"],
        created_at=row["created_at"],
        resolved_by=row["resolution__actor"],
        reason=row["resolution__reason"],
    )
