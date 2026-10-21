from django.core.management.base import BaseCommand
from django.db import connections

# The ids match the tenant_id claims of the demo users in dev/oidc.
DEMO_TENANTS = {
    "11111111-1111-1111-1111-111111111111": "Acme Foods",
    "22222222-2222-2222-2222-222222222222": "Beta Bakery",
}

INSERT_TENANT = """
INSERT INTO tenant (id, name, created_at) VALUES (%s, %s, now())
ON CONFLICT (id) DO NOTHING
"""


class Command(BaseCommand):
    help = "Create the demo tenants. A second run changes nothing (D55)."

    def handle(self, *args, **options) -> None:
        insert_tenants(DEMO_TENANTS)


def insert_tenants(tenants: dict[str, str]) -> None:
    # Tenants are created outside the product, so the owner role writes them (US1).
    with connections["owner"].cursor() as cursor:
        for tenant_id, name in tenants.items():
            cursor.execute(INSERT_TENANT, [tenant_id, name])
