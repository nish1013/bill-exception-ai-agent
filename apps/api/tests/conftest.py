import fcntl
import json
import os
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import redis
from channels.layers import channel_layers
from django.conf import settings
from django.db import connections
from django.test import Client

from config.celery import app
from payables.adapters.broker import ALL_QUEUES, declare_queues
from tests.broker import create_vhost, purge, test_vhost_url
from tests.check_data import seed_po
from tests.tenants import NAMES

GraphQL = Callable[..., Any]

# Children first, so each delete passes the foreign keys.
TABLES = (
    "audit",
    "proposal_action",
    "proposal_exception",
    "proposal",
    "outbox",
    "resolution",
    "exception",
    "check_job_bill",
    "check_job",
    "bill",
    "purchase_order",
    "supplier",
)


@pytest.fixture(scope="session")
def django_db_setup(
    django_test_environment, django_db_blocker, django_db_modify_db_settings, django_db_keepdb
) -> Iterator[None]:
    # The app role cannot create a database, so the owner creates and migrates the test database.
    # django_db_modify_db_settings gives each xdist worker its own database name.
    owner = connections["owner"]
    app = connections["default"]
    original_name = owner.settings_dict["NAME"]
    with django_db_blocker.unblock(), _one_migration_at_a_time():
        owner.creation.create_test_db(
            verbosity=0, autoclobber=True, serialize=False, keepdb=django_db_keepdb
        )
        app.creation.set_as_test_mirror(owner.settings_dict)
        connections["relay"].creation.set_as_test_mirror(owner.settings_dict)
        with owner.cursor() as cursor:
            if django_db_keepdb:
                _delete_rows(cursor)
            for tenant_id, name in NAMES.items():
                cursor.execute(
                    "INSERT INTO tenant (id, name, created_at) VALUES (%s, %s, now()) "
                    "ON CONFLICT (id) DO NOTHING",
                    [tenant_id, name],
                )
    yield
    with django_db_blocker.unblock():
        app.close()
        connections["relay"].close()
        owner.creation.destroy_test_db(original_name, verbosity=0, keepdb=django_db_keepdb)


@pytest.fixture(scope="session", autouse=True)
def channel_layer_prefix() -> str:
    # Each xdist worker sends and reads console events under its own Redis prefix.
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    prefix = f"asgi_test_{worker}"
    settings.CHANNEL_LAYERS["default"]["CONFIG"]["prefix"] = prefix
    return prefix


@pytest.fixture(autouse=True)
def fresh_channel_layer(channel_layer_prefix: str) -> None:
    # Each test runs its sockets on a new event loop. A channels_redis layer keeps
    # asyncio locks bound to the loop that first waited on them, so no layer outlives a test.
    channel_layers.backends.clear()


@pytest.fixture
def fresh_rate_limit() -> Iterator[None]:
    # Each xdist worker counts proposal requests under its own Redis prefix, from zero each test.
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    prefix = f"ratelimit_test_{worker}"
    original = settings.RATE_LIMIT_PREFIX
    settings.RATE_LIMIT_PREFIX = prefix
    client = redis.Redis.from_url(settings.REDIS_URL)
    client.delete(*client.keys(f"{prefix}:*") or [f"{prefix}:none"])
    yield
    settings.RATE_LIMIT_PREFIX = original


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


@contextmanager
def _one_migration_at_a_time() -> Iterator[None]:
    # The migrations alter the app and relay roles, which belong to the cluster. Two workers that
    # alter one role at the same time fail with "tuple concurrently updated".
    with open(Path(tempfile.gettempdir()) / "payables-test-migrate.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _delete_rows(cursor) -> None:
    for table in TABLES:
        cursor.execute(f"DELETE FROM {table}")


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
            _delete_rows(cursor)


@pytest.fixture
def po_100(committed_db) -> None:
    # The example data has PO-100 for B1, so a bill like B1 raises no po_mismatch. The row is
    # stored with no PurchaseOrderAdded event, so the outbox holds only the test's own messages.
    seed_po()


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
    purge(broker_url, *[queue.name for queue in ALL_QUEUES])
    return broker_url
