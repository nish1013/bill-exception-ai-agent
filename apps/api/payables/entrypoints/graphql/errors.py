import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from graphql import GraphQLError

from payables.domain.errors import (
    ConflictError,
    ForbiddenError,
    IdempotencyMismatchError,
    NotFoundError,
    PayablesError,
    RateLimitedError,
    ValidationError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ErrorCode:
    code: str
    status: int


UNAUTHENTICATED = ErrorCode("UNAUTHENTICATED", 401)
RATE_LIMITED = ErrorCode("RATE_LIMITED", 429)
INTERNAL = ErrorCode("INTERNAL", 500)

ERROR_CODES: dict[type[PayablesError], ErrorCode] = {
    ValidationError: ErrorCode("VALIDATION", 400),
    ForbiddenError: ErrorCode("FORBIDDEN", 403),
    NotFoundError: ErrorCode("NOT_FOUND", 404),
    ConflictError: ErrorCode("CONFLICT", 409),
    IdempotencyMismatchError: ErrorCode("IDEMPOTENCY_MISMATCH", 422),
    RateLimitedError: RATE_LIMITED,
}


def format_error(error: Exception) -> dict[str, Any]:
    if not isinstance(error, GraphQLError):
        return {"message": str(error)}
    original = error.original_error
    if original is None:
        return error.formatted

    formatted = error.formatted
    code = code_for(original)
    if code is INTERNAL:
        logger.error("unhandled error in resolver", exc_info=original)
        formatted["message"] = "Internal error"
    formatted["extensions"] = _extensions(code)
    return formatted


def code_for(error: BaseException) -> ErrorCode:
    for cls in type(error).__mro__:
        if cls in ERROR_CODES:
            return ERROR_CODES[cls]
    return INTERNAL


def transport_status(errors: Sequence[GraphQLError] | None) -> int | None:
    # Clients and proxies back off on a real HTTP 429 (D48).
    for error in errors or ():
        if error.original_error is not None and code_for(error.original_error) is RATE_LIMITED:
            return RATE_LIMITED.status
    return None


def unauthenticated_body() -> dict[str, Any]:
    return {"errors": [{"message": "Unauthenticated", "extensions": _extensions(UNAUTHENTICATED)}]}


def _extensions(code: ErrorCode) -> dict[str, Any]:
    return {"code": code.code, "status": code.status}
