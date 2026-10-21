import pytest
from django.db import connections

from tests.check_data import add_bill
from tests.tenants import T1, T2

SUPPLIERS = "query { suppliers { totalCount items { id name vatNumber } } }"

BULK_SUPPLIERS = """
INSERT INTO supplier (id, tenant_id, name, name_norm, created_at)
SELECT gen_random_uuid(), %s, 'Bulk ' || n, 'bulk ' || lpad(n::text, 4, '0'), now()
FROM generate_series(1, %s) AS n
"""


def _suppliers(graphql, token: str) -> dict:
    response = graphql(SUPPLIERS, token)
    assert "errors" not in response.json(), response.json()
    return response.json()["data"]["suppliers"]


def test_d16_suppliers_by_name_own_tenant_only(committed_db, graphql, token_for):
    add_bill("K1", supplier_name="Zed Foods", supplier_vat_number=None)
    add_bill("K2")
    add_bill("K9", T2, supplier_name="Beta Flour", supplier_vat_number=None)

    page = _suppliers(graphql, token_for("c1"))

    assert [(item["name"], item["vatNumber"]) for item in page["items"]] == [
        ("Fresh Farms Ltd", "GB123456789"),
        ("Zed Foods", None),
    ]
    assert page["totalCount"] == 2


@pytest.mark.parametrize("user", ["c1", "a1"])
def test_d16_501_suppliers_list_500_count_501(committed_db, graphql, token_for, user):
    with connections["owner"].cursor() as cursor:
        cursor.execute(BULK_SUPPLIERS, [T1, 501])
        cursor.execute(BULK_SUPPLIERS, [T2, 3])

    page = _suppliers(graphql, token_for(user))

    assert (len(page["items"]), page["totalCount"]) == (500, 501)
