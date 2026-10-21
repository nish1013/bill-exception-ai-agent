from dataclasses import dataclass
from uuid import UUID

from payables.domain.errors import ValidationError
from payables.domain.text import is_blank, letters_and_digits_upper, without_punctuation_lower


@dataclass(frozen=True)
class Supplier:
    id: UUID
    name: str
    vat_number: str | None


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


@dataclass(frozen=True)
class SupplierIdentity:
    name: SupplierName
    vat: VatNumber | None

    @classmethod
    def parse(cls, name: str, vat_number: str | None) -> "SupplierIdentity":
        return cls(name=SupplierName.parse(name), vat=VatNumber.parse(vat_number))
