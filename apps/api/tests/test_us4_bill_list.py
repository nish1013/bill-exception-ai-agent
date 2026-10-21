from tests.check_data import add_bill
from tests.tenants import T2

BILLS = """
query {
  bills { totalCount items { id supplierName invoiceNumber amount currency issueDate hasReceipt } }
}
"""


def _bills(graphql, token: str) -> list[dict]:
    response = graphql(BILLS, token)
    assert "errors" not in response.json(), response.json()
    return response.json()["data"]["bills"]["items"]


def test_us4_bills_listed_newest_first(committed_db, graphql, token_for):
    b1 = add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")

    listed = _bills(graphql, token_for("c1"))

    assert [row["id"] for row in listed] == [str(b2), str(b1)]
    assert listed[1] == {
        "id": str(b1),
        "supplierName": "Fresh Farms Ltd",
        "invoiceNumber": "INV-001",
        "amount": 120000,
        "currency": "GBP",
        "issueDate": "2026-10-01",
        "hasReceipt": True,
    }


def test_i1_t2_bill_not_listed_for_t1(committed_db, graphql, token_for):
    b9 = add_bill("K9", tenant_id=T2)

    assert _bills(graphql, token_for("c1")) == []
    assert [row["id"] for row in _bills(graphql, token_for("c9"))] == [str(b9)]
