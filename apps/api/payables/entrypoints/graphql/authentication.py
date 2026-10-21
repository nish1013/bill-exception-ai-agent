from django.http import HttpRequest

from payables.adapters.identity.claims_mapper import principal_from_claims
from payables.adapters.identity.invalid_token_error import InvalidTokenError
from payables.adapters.identity.jwt_verifier import JwtVerifier
from payables.domain.access import Principal

BEARER = "bearer"


def authenticate(request: HttpRequest, verifier: JwtVerifier) -> Principal:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    token = token.strip()
    if scheme.lower() != BEARER or not token:
        raise InvalidTokenError("no bearer token")
    return principal_from_claims(verifier.verify(token))
