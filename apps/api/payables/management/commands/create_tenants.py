from uuid import UUID

from django.core.management.base import BaseCommand, CommandError, CommandParser

from payables.management.commands.seed_demo import insert_tenants


class Command(BaseCommand):
    help = "Create tenants given as id=name. A second run changes nothing."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("tenants", nargs="+", metavar="id=name")

    def handle(self, *args, **options) -> None:
        insert_tenants(dict(_parse(item) for item in options["tenants"]))


def _parse(item: str) -> tuple[str, str]:
    tenant_id, separator, name = item.partition("=")
    if not separator or not name.strip():
        raise CommandError(f"expected id=name, got {item!r}")
    try:
        return str(UUID(tenant_id)), name.strip()
    except ValueError as error:
        raise CommandError(f"{tenant_id!r} is not a UUID") from error
