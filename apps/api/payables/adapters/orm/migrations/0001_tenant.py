import uuid

from django.db import migrations, models

from payables.adapters.orm.row_level_security import create_app_role, tenant_isolation


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        create_app_role(),
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("name", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "tenant"},
        ),
        # Tenants are created outside the product, so the app role only reads its own row.
        tenant_isolation("tenant", column="id", privileges="SELECT"),
    ]
