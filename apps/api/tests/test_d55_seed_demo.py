from uuid import UUID

import pytest
from django.core.management import CommandError, call_command
from django.db import connections

from tests.tenants import NAMES

pytestmark = pytest.mark.django_db(databases=["default", "owner"])


def _tenants() -> dict:
    with connections["owner"].cursor() as cursor:
        cursor.execute("SELECT id, name FROM tenant")
        return dict(cursor.fetchall())


def test_d55_seed_creates_demo_tenants_once():
    with connections["owner"].cursor() as cursor:
        cursor.execute("DELETE FROM tenant")

    call_command("seed_demo")
    call_command("seed_demo")

    assert _tenants() == NAMES


def test_d55_create_tenants_adds_given_tenants_once():
    e2e = "e2e00000-0000-4000-8000-000000000001"

    call_command("create_tenants", f"{e2e}=E2E Home")
    call_command("create_tenants", f"{e2e}=E2E Home")

    assert _tenants()[UUID(e2e)] == "E2E Home"


@pytest.mark.parametrize(
    "item", ["no-separator", "not-a-uuid=Name", "e2e00000-0000-4000-8000-000000000001= "]
)
def test_d55_create_tenants_refuses_bad_item(item):
    with pytest.raises(CommandError):
        call_command("create_tenants", item)
