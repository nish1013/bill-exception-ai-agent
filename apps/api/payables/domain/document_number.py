from dataclasses import dataclass

from payables.domain.errors import ValidationError
from payables.domain.text_form import letters_and_digits_upper


@dataclass(frozen=True)
class DocumentNumber:
    raw: str
    normalised: str

    @classmethod
    def parse(cls, raw: str, label: str) -> "DocumentNumber":
        normalised = letters_and_digits_upper(raw)
        if not normalised:
            raise ValidationError(f"{label} must hold a letter or a digit")
        return cls(raw=raw.strip(), normalised=normalised)
