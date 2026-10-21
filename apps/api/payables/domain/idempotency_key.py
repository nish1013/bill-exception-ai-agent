from dataclasses import dataclass

from payables.domain.errors import ValidationError

MAX_LENGTH = 255


@dataclass(frozen=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.value) <= MAX_LENGTH or not self.value.isprintable():
            raise ValidationError(f"idempotency key must be 1 to {MAX_LENGTH} printable characters")
