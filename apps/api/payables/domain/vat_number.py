from dataclasses import dataclass

from payables.domain.errors import ValidationError
from payables.domain.text_form import is_blank, letters_and_digits_upper


@dataclass(frozen=True)
class VatNumber:
    normalised: str

    @classmethod
    def parse(cls, raw: str | None) -> "VatNumber | None":
        if is_blank(raw):
            return None
        normalised = letters_and_digits_upper(raw)
        if not normalised:
            raise ValidationError("VAT number must hold a letter or a digit")
        return cls(normalised)
