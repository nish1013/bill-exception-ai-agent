from functools import cache
from typing import Any, Protocol

import jwt
from django.conf import settings
from jwt import PyJWK, PyJWKClient, PyJWKClientConnectionError

from payables.adapters.identity.invalid_token_error import InvalidTokenError

ALGORITHMS = ["RS256"]
REQUIRED_CLAIMS = ["exp", "iss", "aud", "sub"]


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
