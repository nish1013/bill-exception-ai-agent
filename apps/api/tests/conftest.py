import json
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from django.conf import settings
from django.db import connections
from django.test import Client

from tests.tenants import NAMES

GraphQL = Callable[..., Any]

INGEST_TABLES = ("bill", "purchase_order", "supplier")


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker) -> Iterator[None]:
    # The app role cannot create a database, so the owner creates and migrates the test database.
    owner = connections["owner"]
    app = connections["default"]
    original_name = owner.settings_dict["NAME"]
    with django_db_blocker.unblock():
        owner.creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
        app.creation.set_as_test_mirror(owner.settings_dict)
        with owner.cursor() as cursor:
            for tenant_id, name in NAMES.items():
                cursor.execute(
                    "INSERT INTO tenant (id, name, created_at) VALUES (%s, %s, now())",
                    [tenant_id, name],
                )
    yield
    with django_db_blocker.unblock():
        app.close()
        owner.creation.destroy_test_db(original_name, verbosity=0)


@pytest.fixture(scope="session")
def token_for() -> Callable[[str], str]:
    tokens: dict[str, str] = {}

    def fetch(user: str) -> str:
        if user not in tokens:
            form = urllib.parse.urlencode(
                {
                    "grant_type": "client_credentials",
                    "client_id": "payables-tests",
                    "client_secret": "unused",
                    "scope": user,
                }
            ).encode()
            with urllib.request.urlopen(f"{settings.OIDC_ISSUER}/token", form, timeout=5) as r:
                tokens[user] = json.load(r)["access_token"]
        return tokens[user]

    return fetch


@pytest.fixture
def graphql(client: Client) -> GraphQL:
    def post(query: str, token: str | None = None, variables=None, path="/graphql", **headers):
        if token is not None:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        body = {"query": query, "variables": variables or {}}
        return client.post(path, body, content_type="application/json", **headers)

    return post


@pytest.fixture
def committed_db(django_db_setup, django_db_blocker) -> Iterator[None]:
    with django_db_blocker.unblock():
        yield
        with connections["owner"].cursor() as cursor:
            for table in INGEST_TABLES:
                cursor.execute(f"DELETE FROM {table}")
