from dataclasses import dataclass
from typing import Any

from payables.domain.currency_codes import ISO_4217_CODES
from payables.domain.errors import ValidationError

MAX_MINOR_UNITS = 2**63 - 1


@dataclass(frozen=True)
class Money:
    minor_units: int
    currency: str

    def __post_init__(self) -> None:
        _check_minor_units(self.minor_units)
        if self.currency not in ISO_4217_CODES:
            raise ValidationError(f"currency {self.currency!r} is not an ISO 4217 code")


def _check_minor_units(value: Any) -> None:
    # Exact type: bool is an int subclass, and 1200.0 is a float that a client sent (D14).
    if type(value) is not int:
        raise ValidationError("amount must be an integer in minor units")
    if not 0 <= value <= MAX_MINOR_UNITS:
        raise ValidationError(f"amount must be from 0 to {MAX_MINOR_UNITS} minor units")
