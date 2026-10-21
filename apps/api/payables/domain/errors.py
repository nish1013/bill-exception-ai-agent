from typing import ClassVar


class PayablesError(Exception):
    # A request that fails with this error still commits what it wrote before the error.
    keeps_writes: ClassVar[bool] = False


class ConflictError(PayablesError):
    pass


class ResolutionExistsError(ConflictError):
    pass


class StaleProposalError(ConflictError):
    # The approve rolls back. The proposal stays stale, so the 409 keeps that write (D35).
    keeps_writes = True


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
