from typing import Protocol
from uuid import UUID

from payables.domain.checks.exceptions import IgnoreReason


class ResolutionRepository(Protocol):
    def ignore(self, exception_id: UUID, actor: str, reason: IgnoreReason) -> None: ...

    def resolve_by_system(self, exception_ids: list[UUID]) -> None: ...

    def reopen(self, exception_ids: list[UUID]) -> None: ...
