from dataclasses import dataclass

from payables.domain.checks.exception_status import ExceptionStatus
from payables.domain.checks.severity import Severity


@dataclass(frozen=True)
class InboxFilter:
    status: ExceptionStatus | None
    severity: Severity | None

    @classmethod
    def parse(cls, status: str | None, severity: str | None) -> "InboxFilter":
        return cls(
            status=None if status is None else ExceptionStatus.parse(status),
            severity=None if severity is None else Severity.parse(severity),
        )
