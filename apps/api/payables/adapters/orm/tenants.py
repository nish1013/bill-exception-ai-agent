import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from django.db import connection, models, transaction

TENANT_SETTING = "app.tenant_id"
CURRENT_TENANT_SQL = f"NULLIF(current_setting('{TENANT_SETTING}', true), '')::uuid"


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "tenant"


class TenantRepository:
    def find_name(self, tenant_id: UUID) -> str | None:
        return Tenant.objects.filter(id=tenant_id).values_list("name", flat=True).first()


@contextmanager
def tenant_transaction(tenant_id: UUID, lock_timeout_ms: int | None = None) -> Iterator[None]:
    # is_local=true scopes the setting to this transaction, so a pooled connection keeps no tenant.
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config(%s, %s, true)", [TENANT_SETTING, str(tenant_id)])
            if lock_timeout_ms is not None:
                cursor.execute(
                    "SELECT set_config('lock_timeout', %s, true)", [f"{lock_timeout_ms}ms"]
                )
        yield
