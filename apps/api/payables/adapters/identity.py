from collections.abc import Mapping
from functools import cache
from typing import Any, Protocol
from uuid import UUID

import jwt
from django.conf import settings
from jwt import PyJWK, PyJWKClient, PyJWKClientConnectionError

from payables.domain.access import Principal, Role

ALGORITHMS = ["RS256"]
REQUIRED_CLAIMS = ["exp", "iss", "aud", "sub"]
TENANT_CLAIM = "tenant_id"
ROLE_CLAIM = "role"


class InvalidTokenError(Exception):
    pass


class SigningKeySource(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> PyJWK: ...


class JwtVerifier:
    def __init__(self, keys: SigningKeySource, issuer: str, audience: str) -> None:
        self._keys = keys
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> dict[str, Any]:
        try:
            key = self._keys.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                key=key.key,
                algorithms=ALGORITHMS,
                issuer=self._issuer,
                audience=self._audience,
                options={"require": REQUIRED_CLAIMS},
            )
        except PyJWKClientConnectionError:
            raise
        except jwt.PyJWTError as error:
            raise InvalidTokenError(str(error)) from error


@cache
def verifier_from_settings() -> JwtVerifier:
    return JwtVerifier(
        keys=PyJWKClient(settings.OIDC_JWKS_URL),
        issuer=settings.OIDC_ISSUER,
        audience=settings.OIDC_AUDIENCE,
    )


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
