from collections.abc import Mapping
from typing import Any
from uuid import UUID

from payables.adapters.identity.invalid_token_error import InvalidTokenError
from payables.domain.principal import Principal
from payables.domain.role import Role

TENANT_CLAIM = "tenant_id"
ROLE_CLAIM = "role"


def principal_from_claims(claims: Mapping[str, Any]) -> Principal:
    return Principal(
        tenant_id=_tenant_id(claims.get(TENANT_CLAIM)),
        role=_role(claims.get(ROLE_CLAIM)),
        subject=str(claims["sub"]),
    )


def _tenant_id(value: Any) -> UUID:
    if not isinstance(value, str):
        raise InvalidTokenError(f"claim {TENANT_CLAIM} is missing")
    try:
        return UUID(value)
    except ValueError as error:
        raise InvalidTokenError(f"claim {TENANT_CLAIM} is not a UUID") from error


def _role(value: Any) -> Role:
    try:
        return Role(value)
    except ValueError as error:
        raise InvalidTokenError(f"claim {ROLE_CLAIM} is not a known role") from error
