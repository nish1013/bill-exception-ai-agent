import pytest
from django.db import ProgrammingError, connection, transaction

from payables.adapters.orm.tenants import tenant_transaction
from tests.tenants import T1

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("table", ["supplier", "purchase_order", "bill"])
@pytest.mark.parametrize(
    "statement", ["UPDATE {table} SET created_at = now()", "DELETE FROM {table}"]
)
def test_d31_app_role_cannot_change_rows(table, statement):
    with tenant_transaction(T1):
        with pytest.raises(ProgrammingError, match="permission denied"):
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(statement.format(table=table))
