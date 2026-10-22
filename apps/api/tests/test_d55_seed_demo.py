from uuid import UUID

import pytest
from django.core.management import CommandError, call_command
from django.db import connections

from payables.management.commands.seed_demo import check_job_id
from tests.check_data import check
from tests.tenants import NAMES, T1, T2

SEEDED_TABLES = ("supplier", "purchase_order", "bill", "check_job", "check_job_bill", "outbox")

T1_RULES = [
    ("Fresh Farms Ltd", "inv 001", "duplicate"),
    ("Fresh Farms Ltd", "INV-002", "possible_duplicate"),
    ("Northern Packaging Ltd", "NP-7001", "po_mismatch"),
    ("City Cleaning BV", "CC-300", "missing_vat"),
    ("Riverside Logistics", "RL-88", "missing_receipt"),
]
T2_RULES = [
    ("Mill Lane Flour Ltd", "ML 500", "duplicate"),
    ("Dairy Direct Ltd", "DD-41", "missing_receipt"),
]


def _tenants() -> dict:
    with connections["owner"].cursor() as cursor:
        cursor.execute("SELECT id, name FROM tenant")
        return dict(cursor.fetchall())


def _row_counts() -> dict[str, int]:
    with connections["owner"].cursor() as cursor:
        counts = {}
        for table in SEEDED_TABLES:
            cursor.execute(f"SELECT count(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
        return counts


def _job_bills(tenant_id: UUID) -> list[UUID]:
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            "SELECT bill_id FROM check_job_bill WHERE job_id = %s", [check_job_id(tenant_id)]
        )
        return [bill_id for (bill_id,) in cursor.fetchall()]


def _exceptions(tenant_id: UUID) -> list[tuple[str, str, str]]:
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            """
            SELECT s.name, b.invoice_number, e.rule
            FROM exception e JOIN bill b ON b.id = e.bill_id JOIN supplier s ON s.id = b.supplier_id
            WHERE e.tenant_id = %s ORDER BY b.created_at
            """,
            [tenant_id],
        )
        return list(cursor.fetchall())


def test_d55_seed_creates_demo_tenants_and_rows_once(committed_db):
    with connections["owner"].cursor() as cursor:
        cursor.execute("DELETE FROM tenant WHERE id IN (%s, %s)", [T1, T2])

    call_command("seed_demo")
    first = _row_counts()
    call_command("seed_demo")

    assert _tenants() == NAMES
    assert _row_counts() == first
    assert first["check_job"] == 2
    assert first["bill"] == 10


@pytest.mark.parametrize(("tenant_id", "expected"), [(T1, T1_RULES), (T2, T2_RULES)])
def test_d55_seeded_check_raises_each_rule_once_per_tenant(committed_db, tenant_id, expected):
    call_command("seed_demo")

    for tenant in (T1, T2):
        for bill_id in _job_bills(tenant):
            check(check_job_id(tenant), bill_id, tenant)

    assert _exceptions(tenant_id) == expected


@pytest.mark.django_db(databases=["default", "owner"])
def test_d55_create_tenants_adds_given_tenants_once():
    e2e = "e2e00000-0000-4000-8000-000000000001"

    call_command("create_tenants", f"{e2e}=E2E Home")
    call_command("create_tenants", f"{e2e}=E2E Home")

    assert _tenants()[UUID(e2e)] == "E2E Home"


@pytest.mark.django_db(databases=["default", "owner"])
@pytest.mark.parametrize(
    "item", ["no-separator", "not-a-uuid=Name", "e2e00000-0000-4000-8000-000000000001= "]
)
def test_d55_create_tenants_refuses_bad_item(item):
    with pytest.raises(CommandError):
        call_command("create_tenants", item)
