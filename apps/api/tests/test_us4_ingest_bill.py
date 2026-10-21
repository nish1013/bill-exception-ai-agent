import pytest

from payables.adapters.orm.bill import BillRow
from payables.adapters.orm.bill_repository import BillOrmRepository
from payables.adapters.orm.supplier import SupplierRow
from payables.adapters.orm.tenancy import tenant_transaction
from tests.ingest_data import INGEST_BILL, REGISTER_SUPPLIER, bill, error_of
from tests.tenants import T1, T2

pytestmark = pytest.mark.django_db

BILL_LITERAL = """
mutation { ingestBill(idempotencyKey: "K1", bill: {
  supplierName: "Fresh Farms Ltd", invoiceNumber: "INV-001", amount: 1200.50, currency: "GBP",
  issueDate: "2026-10-01", hasReceipt: true }) { billId } }
"""


@pytest.fixture
def ingest(graphql, token_for):
    def call(key: str | None, payload: dict, user: str = "c1"):
        return graphql(INGEST_BILL, token_for(user), {"key": key, "bill": payload})

    return call


def _ingested(response) -> dict:
    assert "errors" not in response.json(), response.json()
    return response.json()["data"]["ingestBill"]


def _bills(tenant_id=T1) -> list[BillRow]:
    with tenant_transaction(tenant_id):
        return list(BillRow.objects.order_by("created_at"))


def _supplier_count(tenant_id=T1) -> int:
    with tenant_transaction(tenant_id):
        return SupplierRow.objects.count()


def test_us4_b1_stored_normalised(graphql, token_for, ingest):
    s1 = graphql(
        REGISTER_SUPPLIER, token_for("c1"), {"name": "Fresh Farms Ltd", "vat": "GB123456789"}
    )
    s1_id = s1.json()["data"]["registerSupplier"]["id"]

    b1 = _ingested(ingest("K1", bill()))

    [row] = _bills()
    assert str(row.id) == b1["billId"]
    assert str(row.supplier_id) == b1["supplierId"] == s1_id
    assert row.invoice_number_norm == "INV001"
    assert (row.amount_minor, row.currency, row.vat_amount_minor) == (120000, "GBP", 20000)
    assert (row.po_number_norm, row.has_receipt) == ("PO100", True)
    assert _supplier_count() == 1


def test_us4_same_key_returns_b1(ingest):
    b1 = _ingested(ingest("K1", bill()))

    again = _ingested(ingest("K1", bill()))

    assert again == b1
    assert len(_bills()) == 1


def test_us4_same_number_new_key_stores_b2(ingest):
    b1 = _ingested(ingest("K1", bill()))

    response = ingest("K2", bill(invoiceNumber="inv 001"))

    b2 = _ingested(response)
    assert b2["billId"] != b1["billId"]
    assert b2["supplierId"] == b1["supplierId"]
    assert [row.invoice_number_norm for row in _bills()] == ["INV001", "INV001"]


def test_us4_unknown_vat_adds_supplier(ingest):
    _ingested(ingest("K1", bill()))

    new_co = _ingested(ingest("K3", bill(supplierName="New Co", supplierVatNumber="GB999")))

    with tenant_transaction(T1):
        supplier = SupplierRow.objects.get(id=new_co["supplierId"])
    assert (supplier.name, supplier.vat_norm) == ("New Co", "GB999")
    assert _supplier_count() == 2
    assert len(_bills()) == 2


@pytest.mark.parametrize("field", ["amount", "vatAmount"])
@pytest.mark.parametrize("value", [1200.50, 1200.0, "1200"])
def test_us4_non_integer_amount_400(ingest, field, value):
    response = ingest("K1", bill(**{field: value}))

    assert response.status_code == 200
    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert _bills() == []
    assert _supplier_count() == 0


def test_us4_literal_amount_1200_50_400(graphql, token_for):
    response = graphql(BILL_LITERAL, token_for("c1"))

    assert response.status_code == 200
    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert _bills() == []


@pytest.mark.parametrize("key", ["", "k" * 256])
def test_us4_empty_key_400(ingest, key):
    response = ingest(key, bill())

    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert _bills() == []


def test_us4_no_key_400(ingest):
    response = ingest(None, bill())

    assert response.status_code == 400
    assert _bills() == []


def test_d26_same_key_other_payload_422(ingest):
    b1 = _ingested(ingest("K1", bill()))

    response = ingest("K1", bill(amount=120001, supplierName="Other Co", supplierVatNumber="GB7"))

    assert error_of(response) == {"code": "IDEMPOTENCY_MISMATCH", "status": 422}
    [row] = _bills()
    assert str(row.id) == b1["billId"]
    assert _supplier_count() == 1


def test_us4_key_scoped_to_tenant(ingest):
    t1_bill = _ingested(ingest("K1", bill()))

    t2_bill = _ingested(ingest("K1", bill(amount=5), user="c9"))

    assert t2_bill["billId"] != t1_bill["billId"]
    assert len(_bills(T1)) == len(_bills(T2)) == 1


def test_us4_approver_403(ingest):
    response = ingest("K1", bill(), user="a1")

    assert error_of(response) == {"code": "FORBIDDEN", "status": 403}
    assert _bills() == []


def test_us1_t2_bill_by_id_not_found_for_t1(ingest):
    t2_bill = _ingested(ingest("K9", bill(), user="c9"))["billId"]

    with tenant_transaction(T1):
        assert BillOrmRepository(T1).find(t2_bill) is None
        assert BillRow.objects.filter(id=t2_bill).count() == 0
