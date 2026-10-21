from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from django.db import connection, transaction

TENANT_SETTING = "app.tenant_id"
CURRENT_TENANT_SQL = f"NULLIF(current_setting('{TENANT_SETTING}', true), '')::uuid"


@contextmanager
def tenant_transaction(tenant_id: UUID) -> Iterator[None]:
    # is_local=true scopes the setting to this transaction, so a pooled connection keeps no tenant.
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config(%s, %s, true)", [TENANT_SETTING, str(tenant_id)])
        yield
