from django.db import migrations

from payables.adapters.orm.row_level_security import create_relay_role

# The relay publishes and cleans up the outbox of each tenant. The sweeper finds stale jobs of
# each tenant, then writes as the app role in a tenant transaction.
RELAY_GRANTS = {
    "outbox": "SELECT, UPDATE, DELETE",
    "check_job": "SELECT",
}


class Migration(migrations.Migration):
    dependencies = [
        ("payables", "0003_checks"),
    ]

    operations = [create_relay_role(RELAY_GRANTS)]
