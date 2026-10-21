from typing import Protocol
from uuid import UUID

from payables.application.read.inbox_filter import InboxFilter
from payables.application.read.inbox_item import InboxItem
from payables.application.read.list_page import ListPage


class InboxQuery(Protocol):
    def worst_first(self, filters: InboxFilter) -> ListPage[InboxItem]: ...

    def find(self, exception_id: UUID) -> InboxItem | None: ...
