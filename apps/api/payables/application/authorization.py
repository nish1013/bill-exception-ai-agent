from payables.domain.access import Principal, Role
from payables.domain.errors import ForbiddenError


def require_role(principal: Principal, role: Role) -> None:
    if principal.role is not role:
        raise ForbiddenError(f"this action needs role {role.value}")
