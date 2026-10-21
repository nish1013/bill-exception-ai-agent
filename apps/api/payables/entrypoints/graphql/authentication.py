from django.http import HttpRequest

from payables.adapters.identity import InvalidTokenError, JwtVerifier, principal_from_claims
from payables.domain.access import Principal

BEARER = "bearer"


def authenticate(request: HttpRequest, verifier: JwtVerifier) -> Principal:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    token = token.strip()
    if scheme.lower() != BEARER or not token:
        raise InvalidTokenError("no bearer token")
    return principal_from_claims(verifier.verify(token))
