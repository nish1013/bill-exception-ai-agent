import base64
import json

import pytest

from payables.adapters.orm.tenants import TenantRepository, tenant_transaction
from tests.tenants import T1, T2

VIEWER = "query { viewer { tenantId tenantName role } }"

pytestmark = pytest.mark.django_db


def test_us1_clerk_runs_for_own_tenant(graphql, token_for):
    response = graphql(VIEWER, token_for("c1"))

    assert response.status_code == 200
    assert response.json()["data"]["viewer"] == {
        "tenantId": str(T1),
        "tenantName": "Acme Foods",
        "role": "clerk",
    }


def test_us1_t2_clerk_runs_for_t2(graphql, token_for):
    response = graphql(VIEWER, token_for("c9"))

    assert response.json()["data"]["viewer"]["tenantName"] == "Beta Bakery"


def test_us1_approver_role_from_claim(graphql, token_for):
    response = graphql(VIEWER, token_for("a1"))

    assert response.json()["data"]["viewer"]["role"] == "approver"


def test_us1_no_tenant_claim_401_reads_nothing(graphql, token_for, django_assert_num_queries):
    with django_assert_num_queries(0):
        response = graphql(VIEWER, token_for("no-tenant"))

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == "Bearer"
    assert response.json()["errors"][0]["extensions"] == {
        "code": "UNAUTHENTICATED",
        "status": 401,
    }
    assert "data" not in response.json()


@pytest.mark.parametrize("authorization", ["", "Bearer", "Bearer ", "Basic abc", "Token abc"])
def test_us1_no_bearer_token_401(client, authorization):
    response = client.post(
        "/graphql",
        {"query": VIEWER},
        content_type="application/json",
        HTTP_AUTHORIZATION=authorization,
    )

    assert response.status_code == 401


def test_us1_token_with_edited_tenant_401(graphql, token_for):
    header, payload, signature = token_for("c1").split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    claims["tenant_id"] = str(T2)
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()

    response = graphql(VIEWER, f"{header}.{forged}.{signature}")

    assert response.status_code == 401


def test_us1_t2_row_by_id_not_found_for_t1():
    with tenant_transaction(T1):
        assert TenantRepository().find_name(T2) is None
        assert TenantRepository().find_name(T1) == "Acme Foods"


def test_us1_tenant_argument_ignored(graphql, token_for):
    response = graphql(
        VIEWER,
        token_for("c1"),
        variables={"tenantId": str(T2)},
        path=f"/graphql?tenantId={T2}&tenant_id={T2}",
        HTTP_X_TENANT_ID=str(T2),
    )

    assert response.status_code == 200
    assert response.json()["data"]["viewer"]["tenantId"] == str(T1)
    assert response.json()["data"]["viewer"]["tenantName"] == "Acme Foods"
