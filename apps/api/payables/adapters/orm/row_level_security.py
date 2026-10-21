from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import migrations

from payables.adapters.orm.tenancy import CURRENT_TENANT_SQL

POLICY = "tenant_isolation"
APP_ALIAS = "default"
RELAY_ALIAS = "relay"
DML = "SELECT, INSERT, UPDATE, DELETE"


def app_role() -> str:
    return settings.DATABASES[APP_ALIAS]["USER"]


def relay_role() -> str:
    return settings.DATABASES[RELAY_ALIAS]["USER"]


def create_app_role() -> migrations.RunPython:
    return migrations.RunPython(_create_app_role, migrations.RunPython.noop)


def create_relay_role(grants: dict[str, str]) -> migrations.RunPython:
    """A login role that bypasses row-level security, with only the given table privileges."""

    def forwards(apps, schema_editor) -> None:
        role = relay_role()
        if role in (app_role(), schema_editor.connection.settings_dict["USER"]):
            raise ImproperlyConfigured("The relay role must differ from the app and owner roles.")
        quoted = _login_role(schema_editor, RELAY_ALIAS)
        schema_editor.execute(
            f"ALTER ROLE {quoted} LOGIN NOSUPERUSER BYPASSRLS NOCREATEDB NOCREATEROLE"
        )
        schema_editor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
        for table, privileges in grants.items():
            schema_editor.execute(
                f"GRANT {privileges} ON {schema_editor.quote_name(table)} TO {quoted}"
            )

    return migrations.RunPython(forwards, migrations.RunPython.noop)


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
    if app_role() == schema_editor.connection.settings_dict["USER"]:
        raise ImproperlyConfigured("The app role must differ from the role that runs migrations.")

    quoted = _login_role(schema_editor, APP_ALIAS)
    schema_editor.execute(
        f"ALTER ROLE {quoted} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
    )
    schema_editor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")


def _login_role(schema_editor, alias: str) -> str:
    role = settings.DATABASES[alias]["USER"]
    quoted = schema_editor.quote_name(role)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
        exists = cursor.fetchone() is not None
    if not exists:
        password = schema_editor.quote_value(settings.DATABASES[alias]["PASSWORD"])
        schema_editor.execute(f"CREATE ROLE {quoted} LOGIN PASSWORD {password}")
    return quoted


def restrictive_policy(table: str, name: str, command: str, using: str) -> migrations.RunSQL:
    # A restrictive policy narrows the tenant policy for one command. It never widens it.
    return migrations.RunSQL(
        f"CREATE POLICY {name} ON {table} AS RESTRICTIVE FOR {command} USING ({using})",
        f"DROP POLICY {name} ON {table}",
    )
