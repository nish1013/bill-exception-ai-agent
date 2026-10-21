from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

# The actor of a check job or a resolution that no user started (D6, D44).
SYSTEM_ACTOR = "system"


class Role(StrEnum):
    CLERK = "clerk"
    APPROVER = "approver"


@dataclass(frozen=True)
class Principal:
    tenant_id: UUID
    role: Role
    subject: str
