from uuid import UUID


def tenant_group(tenant_id: UUID) -> str:
    # A socket joins only the group of its token's tenant (D47).
    return f"tenant.{tenant_id}"
