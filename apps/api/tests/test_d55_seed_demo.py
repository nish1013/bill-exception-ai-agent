import pytest
from django.core.management import call_command
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
