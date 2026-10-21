from enum import StrEnum

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
