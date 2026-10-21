from typing import Protocol

from payables.application.read.inbox_item import InboxItem
from payables.domain.checks.severity import Severity


class InboxQuery(Protocol):
    def worst_first(self, severity: Severity | None) -> list[InboxItem]: ...
