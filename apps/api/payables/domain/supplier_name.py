from dataclasses import dataclass

from payables.domain.errors import ValidationError
from payables.domain.text_form import without_punctuation_lower


@dataclass(frozen=True)
class SupplierName:
    raw: str
    normalised: str

    @classmethod
    def parse(cls, raw: str) -> "SupplierName":
        normalised = without_punctuation_lower(raw)
        if not normalised:
            raise ValidationError("supplier name is empty")
        return cls(raw=raw.strip(), normalised=normalised)
