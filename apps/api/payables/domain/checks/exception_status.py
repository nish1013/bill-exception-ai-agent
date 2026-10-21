from enum import StrEnum

from payables.domain.checks.resolution_kind import ResolutionKind
from payables.domain.errors import ValidationError


class ExceptionStatus(StrEnum):
    OPEN = "open"
    IGNORED = "ignored"
    RESOLVED = "resolved"
    PENDING_SYNC = "pending_sync"

    @classmethod
    def parse(cls, value: str) -> "ExceptionStatus":
        try:
            return cls(value)
        except ValueError as error:
            raise ValidationError(f"status {value!r} is not known") from error


# Status is derived on read from the resolution (D38). No resolution: open.
RESOLUTION_STATUS: dict[ResolutionKind, ExceptionStatus] = {
    ResolutionKind.IGNORE: ExceptionStatus.IGNORED,
    ResolutionKind.SYSTEM: ExceptionStatus.RESOLVED,
}


def status_of(kind: ResolutionKind | None) -> ExceptionStatus:
    return ExceptionStatus.OPEN if kind is None else RESOLUTION_STATUS[kind]


def kinds_with(status: ExceptionStatus) -> list[ResolutionKind]:
    return [kind for kind, kind_status in RESOLUTION_STATUS.items() if kind_status is status]
