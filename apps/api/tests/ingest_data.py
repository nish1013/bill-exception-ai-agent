from datetime import date
from typing import Any

from payables.domain.bill_payload import BillPayload

S1_NAME = "Fresh Farms Ltd"
S1_VAT = "GB123456789"

B1 = {
    "supplierName": S1_NAME,
    "supplierVatNumber": S1_VAT,
    "invoiceNumber": "INV-001",
    "amount": 120000,
    "currency": "GBP",
    "vatAmount": 20000,
    "issueDate": "2026-10-01",
    "poNumber": "PO-100",
    "hasReceipt": True,
}

B1_PAYLOAD = BillPayload(
    supplier_name=S1_NAME,
    supplier_vat_number=S1_VAT,
    invoice_number="INV-001",
    amount=120000,
    currency="GBP",
    vat_amount=20000,
    issue_date=date(2026, 10, 1),
    po_number="PO-100",
    has_receipt=True,
)

REGISTER_SUPPLIER = """
mutation($name: String!, $vat: String) {
  registerSupplier(name: $name, vatNumber: $vat) { id name vatNumber }
}
"""

ADD_PO = """
mutation($number: String!, $supplierId: UUID!, $amount: MinorUnits!, $currency: String!) {
  addPurchaseOrder(poNumber: $number, supplierId: $supplierId, amount: $amount,
                   currency: $currency) { id poNumber supplierId amount currency }
}
"""

INGEST_BILL = """
mutation($key: String!, $bill: BillInput!) {
  ingestBill(idempotencyKey: $key, bill: $bill) { billId supplierId }
}
"""


def bill(**overrides: Any) -> dict[str, Any]:
    return B1 | overrides


def error_of(response) -> dict[str, Any]:
    return response.json()["errors"][0]["extensions"]
