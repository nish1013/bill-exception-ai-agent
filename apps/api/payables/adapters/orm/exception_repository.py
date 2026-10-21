from uuid import UUID

from payables.adapters.orm.exception import ExceptionRow
from payables.domain.checks.exceptions import ResolutionKind, StoredException
from payables.domain.checks.rules import Finding, Rule


class ExceptionOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def add_missing(self, bill_id: UUID, findings: list[Finding]) -> None:
        # A second check of the bill waits on the first one's key, then adds nothing (I6, D5).
        ExceptionRow.objects.bulk_create(
            [
                ExceptionRow(
                    tenant_id=self._tenant_id,
                    bill_id=bill_id,
                    rule=finding.rule.value,
                    fingerprint=finding.fingerprint,
                    related_bill_id=finding.related_bill_id,
                )
                for finding in findings
            ],
            ignore_conflicts=True,
        )

    def on_bill(self, bill_id: UUID) -> list[StoredException]:
        rows = self._rows().filter(bill_id=bill_id).order_by("id")
        return [
            StoredException(
                id=row["id"],
                rule=Rule(row["rule"]),
                fingerprint=row["fingerprint"],
                resolution=_kind(row["resolution__kind"]),
            )
            for row in rows.values("id", "rule", "fingerprint", "resolution__kind")
        ]

    def exists(self, exception_id: UUID) -> bool:
        return self._rows().filter(id=exception_id).exists()

    def bills_with_open(self, rule: Rule, fingerprint: str) -> list[UUID]:
        rows = self._rows().filter(
            rule=rule.value, fingerprint=fingerprint, resolution__isnull=True
        )
        return list(rows.order_by("bill_id").values_list("bill_id", flat=True).distinct())

    def _rows(self):
        return ExceptionRow.objects.filter(tenant_id=self._tenant_id)


def _kind(value: str | None) -> ResolutionKind | None:
    return None if value is None else ResolutionKind(value)
