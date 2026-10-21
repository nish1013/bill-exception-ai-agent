from enum import StrEnum


class Rule(StrEnum):
    DUPLICATE = "duplicate"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    PO_MISMATCH = "po_mismatch"
    MISSING_VAT = "missing_vat"
    MISSING_RECEIPT = "missing_receipt"
