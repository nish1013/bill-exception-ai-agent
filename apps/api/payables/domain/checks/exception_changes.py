from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from payables.domain.checks.finding import Finding
from payables.domain.checks.resolution_kind import ResolutionKind
from payables.domain.checks.stored_exception import StoredException


@dataclass(frozen=True)
class ExceptionChanges:
    to_resolve: list[UUID]
    to_reopen: list[UUID]


def changes_after_check(
    findings: Iterable[Finding], stored: Iterable[StoredException]
) -> ExceptionChanges:
    found = {finding.key for finding in findings}
    to_resolve: list[UUID] = []
    to_reopen: list[UUID] = []
    for exception in stored:
        if exception.key not in found and exception.resolution is None:
            # The problem is gone, so the system resolves it (D6).
            to_resolve.append(exception.id)
        elif exception.key in found and exception.resolution is ResolutionKind.SYSTEM:
            # The problem is back. Only a system resolve reopens: an ignore is final (D5, D29).
            to_reopen.append(exception.id)
    return ExceptionChanges(to_resolve=to_resolve, to_reopen=to_reopen)
