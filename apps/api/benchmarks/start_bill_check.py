import json
import os
import statistics
import time
import urllib.parse
import urllib.request

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402
from django.db import connections  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402

from tests.check_data import add_bill, add_bulk_bills  # noqa: E402
from tests.tenants import NAMES  # noqa: E402

START = """
mutation($ids: [UUID!]!) { startBillCheck(billIds: $ids) { id billCount } }
"""
DATABASE = "bench_payables"
BILLS = 500
RUNS = 5
TARGET_MS = 500


def main() -> None:
    setup_test_environment()
    owner = connections["owner"]
    original_name = owner.settings_dict["NAME"]
    owner.settings_dict["TEST"]["NAME"] = DATABASE
    owner.creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
    for alias in ("default", "relay"):
        connections[alias].creation.set_as_test_mirror(owner.settings_dict)
    try:
        runs = _timed_runs()
    finally:
        for alias in ("default", "relay"):
            connections[alias].close()
        owner.creation.destroy_test_db(original_name, verbosity=0)
    print(
        f"startBillCheck, {BILLS} bills: median {statistics.median(runs):.0f} ms, "
        f"target {TARGET_MS} ms, runs {', '.join(f'{ms:.0f}' for ms in runs)}"
    )


def _timed_runs() -> list[float]:
    with connections["owner"].cursor() as cursor:
        for tenant_id, name in NAMES.items():
            cursor.execute(
                "INSERT INTO tenant (id, name, created_at) VALUES (%s, %s, now())",
                [tenant_id, name],
            )
    add_bill("K1")
    ids = [str(bill_id) for bill_id in add_bulk_bills(BILLS)]
    client = Client()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {_token('c1')}"}

    def start() -> float:
        began = time.perf_counter()
        response = client.post(
            "/graphql",
            {"query": START, "variables": {"ids": ids}},
            content_type="application/json",
            **headers,
        )
        elapsed = (time.perf_counter() - began) * 1000
        assert response.json()["data"]["startBillCheck"]["billCount"] == BILLS, response.json()
        return elapsed

    start()
    return [start() for _ in range(RUNS)]


def _token(user: str) -> str:
    form = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": "payables-tests",
            "client_secret": "unused",
            "scope": user,
        }
    ).encode()
    # The provider takes the issuer from the Host header. The API expects the browser's issuer.
    provider = settings.OIDC_JWKS_URL.removesuffix("/jwks")
    host = urllib.parse.urlsplit(settings.OIDC_ISSUER).netloc
    request = urllib.request.Request(f"{provider}/token", form, headers={"Host": host})
    with urllib.request.urlopen(request, timeout=5) as r:
        return json.load(r)["access_token"]


if __name__ == "__main__":
    main()
