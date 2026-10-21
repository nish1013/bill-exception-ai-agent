import pytest
from django.db import IntegrityError, connections, transaction

from payables.adapters.orm.row_level_security import POLICY, app_role
from payables.adapters.orm.tenancy import tenant_transaction
from tests.tenants import T1, T2

TABLES_WITHOUT_TENANT = {"django_migrations"}

SUPPLIER_INSERT = """
INSERT INTO supplier (id, tenant_id, name, name_norm, created_at)
VALUES (gen_random_uuid(), %s, 'T2 Co', 't2 co', now()) RETURNING id
"""
ROW_INSERTS = {
    "purchase_order": """
        INSERT INTO purchase_order (id, tenant_id, supplier_id, po_number, po_number_norm,
                                    amount_minor, currency, created_at)
        VALUES (gen_random_uuid(), %s, %s, 'PO-1', 'PO1', 1, 'GBP', now())
    """,
    "bill": """
        INSERT INTO bill (id, tenant_id, supplier_id, invoice_number, invoice_number_norm,
                          amount_minor, currency, issue_date, has_receipt, idempotency_key,
                          payload_hash, created_at)
        VALUES (gen_random_uuid(), %s, %s, 'INV-1', 'INV1', 1, 'GBP', '2026-10-01', true, 'K',
                'h', now())
    """,
}

pytestmark = pytest.mark.django_db(databases=["default", "owner"])


def _tenant_ids(alias: str) -> set:
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT id FROM tenant")
        return {row[0] for row in cursor.fetchall()}


def test_i1_app_role_reads_only_session_tenant():
    with tenant_transaction(T1):
        assert _tenant_ids("default") == {T1}


def test_i1_owner_reads_all_so_policy_filters():
    assert {T1, T2} <= _tenant_ids("owner")


def test_i1_app_role_with_no_tenant_reads_nothing():
    assert _tenant_ids("default") == set()


def test_i1_app_role_cannot_bypass_policy():
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", [app_role()]
        )
        assert cursor.fetchone() == (False, False)


def test_i1_each_table_has_tenant_policy():
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
              AND NOT (
                c.relrowsecurity
                AND EXISTS (
                  SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid AND p.polname = %s
                )
              )
            """,
            [POLICY],
        )
        unguarded = {row[0] for row in cursor.fetchall()} - TABLES_WITHOUT_TENANT

    assert unguarded == set()


@pytest.mark.parametrize("table", ["purchase_order", "bill"])
def test_i1_row_cannot_use_other_tenant_supplier(table):
    with connections["owner"].cursor() as cursor:
        cursor.execute(SUPPLIER_INSERT, [T2])
        t2_supplier = cursor.fetchone()[0]
        with pytest.raises(IntegrityError, match="tenant_supplier_fkey"):
            with transaction.atomic(using="owner"):
                cursor.execute(ROW_INSERTS[table], [T1, t2_supplier])
