from dataclasses import dataclass
from uuid import UUID

from payables.domain.role import Role


@dataclass(frozen=True)
class Principal:
    tenant_id: UUID
    role: Role
    subject: str
