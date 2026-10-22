from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CurrencyTotal:
    currency: str
    amount: int


@dataclass(frozen=True)
class TenantReport:
    open_exceptions: int
    money_at_risk: list[CurrencyTotal]


class ReportQuery(Protocol):
    def tenant_report(self) -> TenantReport: ...


def get_report(report: ReportQuery) -> TenantReport:
    return report.tenant_report()
