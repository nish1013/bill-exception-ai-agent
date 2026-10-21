import uuid

import pytest

from payables.adapters.orm.purchase_order import PurchaseOrderRow
from payables.adapters.orm.tenancy import tenant_transaction
from tests.ingest_data import ADD_PO, REGISTER_SUPPLIER, error_of
from tests.tenants import T1

pytestmark = pytest.mark.django_db

PO_LITERAL = """
mutation { addPurchaseOrder(poNumber: "PO-101", supplierId: "%s", amount: %s, currency: "GBP")
  { id } }
"""


@pytest.fixture
def s1(graphql, token_for) -> str:
    response = graphql(
        REGISTER_SUPPLIER, token_for("c1"), {"name": "Fresh Farms Ltd", "vat": "GB1"}
    )
    return response.json()["data"]["registerSupplier"]["id"]


@pytest.fixture
def add_po(graphql, token_for):
    def call(number: str, supplier_id: str, amount=120000, currency="GBP", user="c1"):
        variables = {
            "number": number,
            "supplierId": supplier_id,
            "amount": amount,
            "currency": currency,
        }
        return graphql(ADD_PO, token_for(user), variables)

    return call


def _count() -> int:
    with tenant_transaction(T1):
        return PurchaseOrderRow.objects.count()


def test_us3_po_added(add_po, s1):
    response = add_po("PO-100", s1)

    assert response.json()["data"]["addPurchaseOrder"] | {"id": None} == {
        "id": None,
        "poNumber": "PO-100",
        "supplierId": s1,
        "amount": 120000,
        "currency": "GBP",
    }
    assert _count() == 1


@pytest.mark.parametrize("again", ["po 100", "PO-100", "PO100"])
def test_us3_same_number_409(add_po, s1, again):
    add_po("PO-100", s1)

    response = add_po(again, s1)

    assert error_of(response) == {"code": "CONFLICT", "status": 409}
    assert _count() == 1


@pytest.mark.parametrize("amount", [1200.50, 1200.0, "1200", True])
def test_us3_non_integer_amount_400(add_po, s1, amount):
    response = add_po("PO-100", s1, amount=amount)

    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert _count() == 0


@pytest.mark.parametrize("amount", ["1200.50", '"1200"', "true"])
def test_us3_literal_amount_400(graphql, token_for, s1, amount):
    response = graphql(PO_LITERAL % (s1, amount), token_for("c1"))

    assert response.status_code == 200
    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert _count() == 0


@pytest.mark.parametrize("currency", ["XXX1", "gbp", "ZZZ"])
def test_us3_bad_currency_400(add_po, s1, currency):
    response = add_po("PO-100", s1, currency=currency)

    assert error_of(response) == {"code": "VALIDATION", "status": 400}


def test_us3_unknown_supplier_404(add_po):
    response = add_po("PO-100", str(uuid.uuid4()))

    assert error_of(response) == {"code": "NOT_FOUND", "status": 404}


def test_us3_t2_supplier_404(graphql, token_for, add_po):
    t2 = graphql(REGISTER_SUPPLIER, token_for("c9"), {"name": "Fresh Farms Ltd", "vat": "GB1"})
    t2_supplier = t2.json()["data"]["registerSupplier"]["id"]

    response = add_po("PO-100", t2_supplier)

    assert error_of(response) == {"code": "NOT_FOUND", "status": 404}
    assert _count() == 0


def test_us3_approver_403(add_po, s1):
    response = add_po("PO-100", s1, user="a1")

    assert error_of(response) == {"code": "FORBIDDEN", "status": 403}
