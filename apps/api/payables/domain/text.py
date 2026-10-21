import unicodedata
from dataclasses import dataclass

from payables.domain.errors import ValidationError


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


def letters_and_digits_upper(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", value).upper() if char.isalnum())


def without_punctuation_lower(value: str) -> str:
    folded = unicodedata.normalize("NFKC", value).casefold()
    kept = "".join(char for char in folded if not unicodedata.category(char).startswith("P"))
    return " ".join(kept.split())


def is_blank(value: str | None) -> bool:
    return value is None or not value.strip()
