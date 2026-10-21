from uuid import UUID

from payables.application.authorization import require_role
from payables.application.ports.exception_repository import ExceptionRepository
from payables.application.ports.resolution_repository import ResolutionRepository
from payables.domain.access import Principal, Role
from payables.domain.checks.exceptions import IgnoreReason
from payables.domain.errors import NotFoundError


def ignore_exception(
    principal: Principal,
    exception_id: UUID,
    reason: str,
    exceptions: ExceptionRepository,
    resolutions: ResolutionRepository,
) -> None:
    require_role(principal, Role.CLERK)
    parsed = IgnoreReason.parse(reason)
    if not exceptions.exists(exception_id):
        raise NotFoundError("exception not found")
    # The key on the exception id refuses a second resolution with a conflict (I7).
    resolutions.ignore(exception_id, principal.subject, parsed)
