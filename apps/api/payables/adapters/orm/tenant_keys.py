from django.db import migrations


def tenant_foreign_key(table: str, column: str, target: str) -> migrations.RunSQL:
    # (tenant_id, <column>) refers to <target> (tenant_id, id), so both rows share a tenant (I1).
    name = f"{table}_tenant_{column}_fkey"
    return migrations.RunSQL(
        f"ALTER TABLE {table} ADD CONSTRAINT {name} "
        f"FOREIGN KEY (tenant_id, {column}) REFERENCES {target} (tenant_id, id)",
        f"ALTER TABLE {table} DROP CONSTRAINT {name}",
    )
