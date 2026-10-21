from dataclasses import dataclass

from payables.domain.errors import ValidationError

MAX_LENGTH = 1000


@dataclass(frozen=True)
class IgnoreReason:
    text: str

    @classmethod
    def parse(cls, raw: str) -> "IgnoreReason":
        text = raw.strip()
        if not text:
            raise ValidationError("an ignore needs a reason")
        if len(text) > MAX_LENGTH:
            raise ValidationError(f"a reason has at most {MAX_LENGTH} characters")
        return cls(text)
