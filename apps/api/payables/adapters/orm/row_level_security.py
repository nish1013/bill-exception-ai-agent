from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import migrations

from payables.adapters.orm.tenancy import CURRENT_TENANT_SQL

POLICY = "tenant_isolation"
APP_ALIAS = "default"
DML = "SELECT, INSERT, UPDATE, DELETE"


def app_role() -> str:
    return settings.DATABASES[APP_ALIAS]["USER"]


def create_app_role() -> migrations.RunPython:
    return migrations.RunPython(_create_app_role, migrations.RunPython.noop)


def tenant_isolation(
    table: str, column: str = "tenant_id", privileges: str = DML
) -> migrations.RunPython:
    def forwards(apps, schema_editor) -> None:
        name = schema_editor.quote_name(table)
        check = f"{schema_editor.quote_name(column)} = {CURRENT_TENANT_SQL}"
        schema_editor.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
        schema_editor.execute(
            f"CREATE POLICY {POLICY} ON {name} USING ({check}) WITH CHECK ({check})"
        )
        schema_editor.execute(
            f"GRANT {privileges} ON {name} TO {schema_editor.quote_name(app_role())}"
        )

    return migrations.RunPython(forwards, migrations.RunPython.noop)


def _create_app_role(apps, schema_editor) -> None:
    role = app_role()
    if role == schema_editor.connection.settings_dict["USER"]:
        raise ImproperlyConfigured("The app role must differ from the role that runs migrations.")

    quoted = schema_editor.quote_name(role)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
        exists = cursor.fetchone() is not None

    if not exists:
        password = schema_editor.quote_value(settings.DATABASES[APP_ALIAS]["PASSWORD"])
        schema_editor.execute(f"CREATE ROLE {quoted} LOGIN PASSWORD {password}")
    schema_editor.execute(
        f"ALTER ROLE {quoted} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
    )
    schema_editor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
