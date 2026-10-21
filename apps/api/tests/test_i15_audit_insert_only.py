import uuid

import pytest
from django.db import ProgrammingError, connections, transaction

from payables.adapters.orm.tenants import tenant_transaction
from tests.concurrency import owner_count
from tests.tenants import T1

INSERT = (
    "INSERT INTO audit (id, tenant_id, proposal_id, actor, kind, payload, created_at) "
    "VALUES (%s, %s, NULL, 'agent', 'model_input', '{}', now())"
)


def _as_app_role(sql: str, params: list | None = None) -> None:
    with tenant_transaction(T1):
        with connections["default"].cursor() as cursor:
            cursor.execute(sql, params or [])


@pytest.fixture
def record(committed_db) -> uuid.UUID:
    record_id = uuid.uuid4()
    _as_app_role(INSERT, [record_id, T1])
    return record_id


def test_i15_app_role_inserts_audit(record):
    assert owner_count("audit", "id = %s", [record]) == 1


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit SET actor = 'someone' WHERE id = %s",
        "DELETE FROM audit WHERE id = %s",
        "SELECT payload FROM audit WHERE id = %s",
    ],
)
def test_i15_app_role_cannot_change_remove_or_read_audit(record, sql):
    with pytest.raises(ProgrammingError, match="permission denied for table audit"):
        _as_app_role(sql, [record])

    assert owner_count("audit", "id = %s AND actor = 'agent'", [record]) == 1


def test_i15_relay_role_cannot_touch_audit(record):
    with pytest.raises(ProgrammingError, match="permission denied for table audit"):
        with transaction.atomic(using="relay"), connections["relay"].cursor() as cursor:
            cursor.execute("DELETE FROM audit WHERE id = %s", [record])
