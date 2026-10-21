import pytest
from graphql import GraphQLError

from payables.domain.errors import (
    ConflictError,
    ForbiddenError,
    IdempotencyMismatchError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)
from payables.entrypoints.graphql.errors import format_error, transport_status


class StaleProposalError(ConflictError):
    pass


def _resolver_error(original: Exception) -> GraphQLError:
    return GraphQLError(str(original), original_error=original)


@pytest.mark.parametrize(
    ("error", "code", "status"),
    [
        (ValidationError("amount is a float"), "VALIDATION", 400),
        (ForbiddenError("wrong role"), "FORBIDDEN", 403),
        (NotFoundError("no such bill"), "NOT_FOUND", 404),
        (ConflictError("not pending"), "CONFLICT", 409),
        (StaleProposalError("stale"), "CONFLICT", 409),
        (IdempotencyMismatchError("other payload"), "IDEMPOTENCY_MISMATCH", 422),
        (RateLimitedError("over quota"), "RATE_LIMITED", 429),
    ],
)
def test_d48_error_carries_code_and_status(error, code, status):
    formatted = format_error(_resolver_error(error))

    assert formatted["extensions"] == {"code": code, "status": status}
    assert formatted["message"] == str(error)


def test_d48_unknown_error_hides_its_text():
    formatted = format_error(_resolver_error(RuntimeError("password=secret")))

    assert formatted["message"] == "Internal error"
    assert formatted["extensions"] == {"code": "INTERNAL", "status": 500}


def test_d48_document_error_left_as_is():
    assert "extensions" not in format_error(GraphQLError("Cannot query field 'x'"))


def test_d48_rate_limit_is_http_429():
    errors = [_resolver_error(ConflictError("a")), _resolver_error(RateLimitedError("b"))]

    assert transport_status(errors) == 429


@pytest.mark.parametrize(
    "errors", [None, [], [GraphQLError("syntax")], [_resolver_error(ForbiddenError("x"))]]
)
def test_d48_other_errors_keep_status(errors):
    assert transport_status(errors) is None
