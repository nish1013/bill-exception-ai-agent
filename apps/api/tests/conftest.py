import json
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from django.conf import settings
from django.db import connections
from django.test import Client

from config.celery import app
from payables.adapters.broker.queues import CHECKS, dead_letter_name, declare_queues
from tests.broker import create_vhost, purge, test_vhost_url
from tests.tenants import NAMES

GraphQL = Callable[..., Any]

# Children first, so each delete passes the foreign keys.
TABLES = (
    "outbox",
    "exception",
    "check_job_bill",
    "check_job",
    "bill",
    "purchase_order",
    "supplier",
)


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker) -> Iterator[None]:
    # The app role cannot create a database, so the owner creates and migrates the test database.
    owner = connections["owner"]
    app = connections["default"]
    original_name = owner.settings_dict["NAME"]
    with django_db_blocker.unblock():
        owner.creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
        app.creation.set_as_test_mirror(owner.settings_dict)
        connections["relay"].creation.set_as_test_mirror(owner.settings_dict)
        with owner.cursor() as cursor:
            for tenant_id, name in NAMES.items():
                cursor.execute(
                    "INSERT INTO tenant (id, name, created_at) VALUES (%s, %s, now())",
                    [tenant_id, name],
                )
    yield
    with django_db_blocker.unblock():
        app.close()
        connections["relay"].close()
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
            with urllib.request.urlopen(_token_request(form), timeout=5) as r:
                tokens[user] = json.load(r)["access_token"]
        return tokens[user]

    return fetch


def _token_request(form: bytes) -> urllib.request.Request:
    # The API reaches the provider at another host than the browser. The provider takes the
    # issuer from the Host header, so the token gets the issuer that the browser sees.
    provider = settings.OIDC_JWKS_URL.removesuffix("/jwks")
    host = urllib.parse.urlsplit(settings.OIDC_ISSUER).netloc
    return urllib.request.Request(f"{provider}/token", form, headers={"Host": host})


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
            for table in TABLES:
                cursor.execute(f"DELETE FROM {table}")


@pytest.fixture(scope="session")
def broker_url(django_db_setup) -> str:
    create_vhost(settings.CELERY_BROKER_URL)
    url = test_vhost_url(settings.CELERY_BROKER_URL)
    # broker_url keeps the Django setting's value. Celery connects with the read and write URLs.
    app.conf.update(broker_write_url=url, broker_read_url=url)
    return url


@pytest.fixture
def queues(broker_url) -> str:
    with app.connection_for_write() as connection:
        declare_queues(connection)
    purge(broker_url, CHECKS, dead_letter_name(CHECKS))
    return broker_url
