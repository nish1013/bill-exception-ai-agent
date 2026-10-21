import pytest
from django.db import ProgrammingError, connections, transaction

from payables.adapters.orm.row_level_security import RELAY_ALIAS, relay_role
from tests.check_data import add_bill, start_job
from tests.tenants import T1, T2

NOT_GRANTED = ["tenant", "supplier", "purchase_order", "bill", "exception", "check_job_bill"]


def _relay_query(sql: str) -> list:
    with transaction.atomic(using=RELAY_ALIAS), connections[RELAY_ALIAS].cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall() if cursor.description else []


def test_d7_relay_reads_outbox_of_each_tenant(committed_db):
    start_job([add_bill("K1")])
    start_job([add_bill("K9", tenant_id=T2)], tenant_id=T2)

    rows = _relay_query("SELECT DISTINCT tenant_id FROM outbox")

    assert {row[0] for row in rows} == {T1, T2}


@pytest.mark.parametrize("table", NOT_GRANTED)
def test_d7_relay_cannot_read_other_tables(committed_db, table):
    with pytest.raises(ProgrammingError, match="permission denied"):
        _relay_query(f"SELECT 1 FROM {table}")


@pytest.mark.parametrize(
    "statement", ["UPDATE check_job SET status = 'failed'", "INSERT INTO outbox DEFAULT VALUES"]
)
def test_d7_relay_cannot_write_beyond_grants(committed_db, statement):
    with pytest.raises(ProgrammingError, match="permission denied"):
        _relay_query(statement)


def test_d7_relay_role_is_no_superuser(committed_db):
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles "
            "WHERE rolname = %s",
            [relay_role()],
        )
        assert cursor.fetchone() == (False, True, False, False)
