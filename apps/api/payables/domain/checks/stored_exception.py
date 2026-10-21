from dataclasses import dataclass
from uuid import UUID

from payables.domain.checks.resolution_kind import ResolutionKind
from payables.domain.checks.rule import Rule


@dataclass(frozen=True)
class StoredException:
    id: UUID
    rule: Rule
    fingerprint: str
    resolution: ResolutionKind | None

    @property
    def key(self) -> tuple[Rule, str]:
        return (self.rule, self.fingerprint)
