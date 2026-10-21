import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK

from payables.adapters.identity.invalid_token_error import InvalidTokenError
from payables.adapters.identity.jwt_verifier import JwtVerifier

ISSUER = "http://oidc.test/payables"
AUDIENCE = "payables-api"

PROVIDER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FixedKey:
    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        return PyJWK.from_dict(
            jwt.algorithms.RSAAlgorithm.to_jwk(PROVIDER_KEY.public_key(), as_dict=True)
            | {"alg": "RS256"}
        )


def _claims(**overrides) -> dict:
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "c1", "iat": now, "exp": now + 60}
    claims.update(overrides)
    return {key: value for key, value in claims.items() if value is not None}


def _sign(claims: dict, key=PROVIDER_KEY, algorithm="RS256") -> str:
    return jwt.encode(claims, key, algorithm=algorithm)


VERIFIER = JwtVerifier(FixedKey(), ISSUER, AUDIENCE)


def test_us1_valid_token_gives_claims():
    assert VERIFIER.verify(_sign(_claims(role="clerk")))["role"] == "clerk"


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(_sign(_claims(), key=OTHER_KEY), id="other-key"),
        pytest.param(_sign(_claims(exp=int(time.time()) - 1)), id="expired"),
        pytest.param(_sign(_claims(iss="http://evil.test/payables")), id="issuer"),
        pytest.param(_sign(_claims(aud="other-api")), id="audience"),
        pytest.param(_sign(_claims(exp=None)), id="no-exp"),
        pytest.param(_sign(_claims(sub=None)), id="no-sub"),
        pytest.param(
            _sign(_claims(), key="shared-secret-at-least-32-bytes!", algorithm="HS256"), id="hs256"
        ),
        pytest.param(_sign(_claims(), key=None, algorithm="none"), id="alg-none"),
        pytest.param("not-a-jwt", id="garbage"),
    ],
)
def test_us1_bad_token_refused(token):
    with pytest.raises(InvalidTokenError):
        VERIFIER.verify(token)
