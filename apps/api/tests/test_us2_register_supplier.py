import pytest

from payables.adapters.orm.suppliers import SupplierRow
from payables.adapters.orm.tenants import tenant_transaction
from tests.ingest_data import REGISTER_SUPPLIER, error_of
from tests.tenants import T1, T2

pytestmark = pytest.mark.django_db


@pytest.fixture
def register(graphql, token_for):
    def call(name: str, vat: str | None = None, user: str = "c1"):
        return graphql(REGISTER_SUPPLIER, token_for(user), {"name": name, "vat": vat})

    return call


def _supplier(response) -> dict:
    return response.json()["data"]["registerSupplier"]


def _count(tenant_id) -> int:
    with tenant_transaction(tenant_id):
        return SupplierRow.objects.count()


def test_us2_new_vat_normalised(register):
    s1 = _supplier(register("Fresh Farms Ltd", "gb 123 456 789"))

    assert s1["name"] == "Fresh Farms Ltd"
    assert s1["vatNumber"] == "GB123456789"
    assert _count(T1) == 1


def test_us2_same_vat_returns_s1(register):
    s1 = _supplier(register("Fresh Farms Ltd", "GB123456789"))

    again = _supplier(register("Fresh Farms Limited", "GB123456789"))

    assert again == s1
    assert _count(T1) == 1


def test_us2_same_name_no_vat_returns_it(register):
    green = _supplier(register("Green Co"))

    again = _supplier(register("GREEN CO."))

    assert again == green
    assert again["name"] == "Green Co"
    assert _count(T1) == 1


def test_us2_suffix_gives_new_supplier(register):
    register("Green Co")

    register("Green Co Ltd")

    assert _count(T1) == 2


def test_us2_tenants_share_no_supplier(register):
    t2_supplier = _supplier(register("Fresh Farms Ltd", "GB123456789", user="c9"))

    t1_supplier = _supplier(register("Fresh Farms Ltd", "GB123456789"))

    assert t1_supplier["id"] != t2_supplier["id"]
    assert _count(T1) == 1
    assert _count(T2) == 1


@pytest.mark.parametrize("name", ["", "   ", "..."])
def test_us2_empty_name_400(register, name):
    response = register(name, "GB123456789")

    assert response.status_code == 200
    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert _count(T1) == 0


def test_us2_approver_403(register):
    response = register("Fresh Farms Ltd", "GB123456789", user="a1")

    assert error_of(response) == {"code": "FORBIDDEN", "status": 403}
    assert _count(T1) == 0
