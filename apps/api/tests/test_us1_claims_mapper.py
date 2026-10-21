import pytest

from payables.adapters.identity import InvalidTokenError, principal_from_claims
from payables.domain.access import Principal, Role
from tests.tenants import T1


def test_us1_claims_give_tenant_and_role():
    claims = {"sub": "c1", "tenant_id": str(T1), "role": "clerk"}

    assert principal_from_claims(claims) == Principal(T1, Role.CLERK, "c1")


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param({"sub": "c1", "role": "clerk"}, id="no-tenant"),
        pytest.param({"sub": "c1", "tenant_id": "", "role": "clerk"}, id="empty-tenant"),
        pytest.param({"sub": "c1", "tenant_id": "T1", "role": "clerk"}, id="tenant-not-uuid"),
        pytest.param({"sub": "c1", "tenant_id": 1, "role": "clerk"}, id="tenant-not-string"),
        pytest.param({"sub": "c1", "tenant_id": str(T1)}, id="no-role"),
        pytest.param({"sub": "c1", "tenant_id": str(T1), "role": "admin"}, id="unknown-role"),
        pytest.param({"sub": "c1", "tenant_id": str(T1), "role": "Clerk"}, id="role-case"),
    ],
)
def test_us1_bad_claims_refused(claims):
    with pytest.raises(InvalidTokenError):
        principal_from_claims(claims)
