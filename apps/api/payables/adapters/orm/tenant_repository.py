from uuid import UUID

from payables.adapters.orm.tenant import Tenant


class TenantRepository:
    def find_name(self, tenant_id: UUID) -> str | None:
        return Tenant.objects.filter(id=tenant_id).values_list("name", flat=True).first()
