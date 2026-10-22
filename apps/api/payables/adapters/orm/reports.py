from functools import reduce
from operator import or_
from uuid import UUID

from django.db.models import Exists, OuterRef, Q, Sum

from payables.adapters.orm.bills import BillRow
from payables.adapters.orm.exceptions import ExceptionRow, with_status
from payables.application.reports import CurrencyTotal, TenantReport
from payables.domain.checks.exceptions import ExceptionStatus
from payables.domain.reports import AT_RISK_STATUSES


class ReportOrmQuery:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def tenant_report(self) -> TenantReport:
        exceptions = ExceptionRow.objects.filter(tenant_id=self._tenant_id)
        at_risk = exceptions.filter(_any_status(AT_RISK_STATUSES), bill_id=OuterRef("pk"))
        # A filter on Exists keeps one row for each bill, whatever its number of exceptions (D13).
        totals = (
            BillRow.objects.filter(Exists(at_risk), tenant_id=self._tenant_id)
            .values("currency")
            .annotate(amount=Sum("amount_minor"))
            .order_by("currency")
        )
        return TenantReport(
            open_exceptions=exceptions.filter(with_status(ExceptionStatus.OPEN)).count(),
            money_at_risk=[CurrencyTotal(row["currency"], row["amount"]) for row in totals],
        )


def _any_status(statuses: tuple[ExceptionStatus, ...]) -> Q:
    return reduce(or_, [with_status(status) for status in statuses])
