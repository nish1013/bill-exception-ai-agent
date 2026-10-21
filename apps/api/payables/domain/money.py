from dataclasses import dataclass
from typing import Any

from payables.domain.errors import ValidationError

MAX_MINOR_UNITS = 2**63 - 1

ISO_4217_CODES = frozenset(
    """
    AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN BWP
    BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP
    GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR
    KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK
    MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR
    SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS
    UAH UGX USD UYU UZS VES VND VUV WST XAF XCD XCG XOF XPF YER ZAR ZMW ZWG
    """.split()
)


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
