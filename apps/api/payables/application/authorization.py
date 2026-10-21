from payables.domain.errors import ForbiddenError
from payables.domain.principal import Principal
from payables.domain.role import Role


def require_role(principal: Principal, role: Role) -> None:
    if principal.role is not role:
        raise ForbiddenError(f"this action needs role {role.value}")
