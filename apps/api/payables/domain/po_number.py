from payables.domain.document_number import DocumentNumber
from payables.domain.text_form import is_blank


def po_number(raw: str) -> DocumentNumber:
    return DocumentNumber.parse(raw, "PO number")


def optional_po_number(raw: str | None) -> DocumentNumber | None:
    return None if is_blank(raw) else po_number(raw)
