from payables.domain.document_number import DocumentNumber


def invoice_number(raw: str) -> DocumentNumber:
    return DocumentNumber.parse(raw, "invoice number")
