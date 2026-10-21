class PayablesError(Exception):
    pass


class ConflictError(PayablesError):
    pass


class ForbiddenError(PayablesError):
    pass


class IdempotencyMismatchError(PayablesError):
    pass


class NotFoundError(PayablesError):
    pass


class RateLimitedError(PayablesError):
    pass


class ValidationError(PayablesError):
    pass
