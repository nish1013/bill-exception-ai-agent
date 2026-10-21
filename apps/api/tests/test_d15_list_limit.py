from uuid import UUID

import pytest
from django.db import connections

from tests.check_data import add_bill
from tests.tenants import T2

BILLS = "query { bills { totalCount items { id } } }"
INBOX = """
query($severity: String) { exceptions(severity: $severity) { totalCount items { id } } }
"""

BULK_BILLS = """
INSERT INTO bill (id, tenant_id, supplier_id, invoice_number, invoice_number_norm, amount_minor,
                  currency, issue_date, has_receipt, idempotency_key, payload_hash, created_at)
SELECT gen_random_uuid(), tenant_id, supplier_id, 'INV-' || n, 'INV' || n, 100 + n, 'GBP',
       '2026-10-01', true, 'bulk-' || n, 'h', now()
FROM bill, generate_series(1, %s) AS n
WHERE id = %s
"""
BULK_EXCEPTIONS = """
INSERT INTO exception (id, tenant_id, bill_id, rule, fingerprint, created_at)
SELECT gen_random_uuid(), tenant_id, id, 'missing_receipt', 'bulk-' || n, now()
FROM bill, generate_series(1, %s) AS n
WHERE id = %s
"""


def _bulk(sql: str, bill_id: UUID, count: int) -> None:
    with connections["owner"].cursor() as cursor:
        cursor.execute(sql, [count, bill_id])


def _page(graphql, token: str, query: str, field: str, **variables) -> tuple[int, int]:
    response = graphql(query, token, variables)
    assert "errors" not in response.json(), response.json()
    page = response.json()["data"][field]
    return len(page["items"]), page["totalCount"]


@pytest.fixture
def tenants_with_rows(committed_db) -> None:
    t1_bill = add_bill("K1")
    t2_bill = add_bill("K9", tenant_id=T2)
    _bulk(BULK_BILLS, t1_bill, 500)
    _bulk(BULK_BILLS, t2_bill, 2)
    _bulk(BULK_EXCEPTIONS, t1_bill, 501)
    _bulk(BULK_EXCEPTIONS, t2_bill, 2)


def test_d15_501_bills_list_500_count_501(tenants_with_rows, graphql, token_for):
    assert _page(graphql, token_for("c1"), BILLS, "bills") == (500, 501)


def test_d15_501_exceptions_list_500_count_501(tenants_with_rows, graphql, token_for):
    assert _page(graphql, token_for("c1"), INBOX, "exceptions") == (500, 501)


def test_d15_count_uses_the_filter(tenants_with_rows, graphql, token_for):
    assert _page(graphql, token_for("c1"), INBOX, "exceptions", severity="high") == (0, 0)


def test_i1_count_holds_no_other_tenant_rows(tenants_with_rows, graphql, token_for):
    c9 = token_for("c9")

    assert _page(graphql, c9, BILLS, "bills") == (3, 3)
    assert _page(graphql, c9, INBOX, "exceptions") == (2, 2)
