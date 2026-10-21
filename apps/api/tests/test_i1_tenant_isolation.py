import pytest
from django.db import connections

from payables.adapters.orm.row_level_security import POLICY, app_role
from payables.adapters.orm.tenancy import tenant_transaction
from tests.tenants import T1, T2

TABLES_WITHOUT_TENANT = {"django_migrations"}

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
