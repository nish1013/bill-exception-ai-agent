from uuid import UUID

from payables.adapters.orm.exception import ExceptionRow
from payables.domain.checks.finding import Finding


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
