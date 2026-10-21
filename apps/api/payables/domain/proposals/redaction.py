import re
from collections.abc import Callable

REDACTED = "[redacted]"

IBAN_SHAPE = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b")
CARD_SHAPE = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
SORT_CODE_AND_ACCOUNT = re.compile(r"\b\d{2}[- ]?\d{2}[- ]?\d{2}[\s,;/]+\d{8}\b")
LABELLED_BANK_NUMBER = re.compile(
    r"(?i)\b(?:account|acct|a/c|sort\s*code|routing)"
    r"(?:\s*(?:no|number|num|code|#))?\.?[\s:#-]*\d[\d -]{4,30}\d\b"
)
BIC = re.compile(r"(?i:\b(?:swift|bic)(?:\s*code)?[\s:#-]*)[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
SECRETS = (
    re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\bbearer\s+[\w.~+/-]+=*"),
    re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|token)\s*[:=]\s*\S+"),
)


def redact(text: str) -> str:
    """Remove bank details, card numbers, email addresses and secrets from text for the model."""
    for pattern in SECRETS:
        text = pattern.sub(REDACTED, text)
    text = EMAIL.sub(REDACTED, text)
    text = LABELLED_BANK_NUMBER.sub(REDACTED, text)
    text = BIC.sub(REDACTED, text)
    text = SORT_CODE_AND_ACCOUNT.sub(REDACTED, text)
    text = _sub_valid(IBAN_SHAPE, _has_iban_prefix, text)
    return _sub_valid(CARD_SHAPE, _passes_luhn, text)


def _sub_valid(pattern: re.Pattern[str], is_valid: Callable[[str], bool], text: str) -> str:
    # A shape alone matches PO and invoice numbers too. Only a checksum match is a bank number.
    return pattern.sub(lambda m: REDACTED if is_valid(m.group(0)) else m.group(0), text)


def _has_iban_prefix(candidate: str) -> bool:
    # The shape can take the next word as well, so each length from 15 to 34 is tried.
    compact = candidate.replace(" ", "")
    return any(_iban_checksum_ok(compact[:end]) for end in range(15, min(len(compact), 34) + 1))


def _iban_checksum_ok(iban: str) -> bool:
    moved = iban[4:] + iban[:4]
    digits = "".join(str(int(char, 36)) for char in moved)
    return int(digits) % 97 == 1


def _passes_luhn(candidate: str) -> bool:
    digits = [int(char) for char in candidate if char.isdigit()]
    total = 0
    for position, digit in enumerate(reversed(digits)):
        if position % 2 == 1:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0
