from dataclasses import dataclass

from payables.domain.supplier_name import SupplierName
from payables.domain.vat_number import VatNumber


@dataclass(frozen=True)
class SupplierIdentity:
    name: SupplierName
    vat: VatNumber | None

    @classmethod
    def parse(cls, name: str, vat_number: str | None) -> "SupplierIdentity":
        return cls(name=SupplierName.parse(name), vat=VatNumber.parse(vat_number))
