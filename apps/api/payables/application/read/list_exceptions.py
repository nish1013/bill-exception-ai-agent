from uuid import UUID

from payables.application.ports.inbox_query import InboxQuery
from payables.application.read.inbox_filter import InboxFilter
from payables.application.read.inbox_item import InboxItem
from payables.application.read.list_page import ListPage
from payables.domain.errors import NotFoundError


def list_exceptions(filters: InboxFilter, inbox: InboxQuery) -> ListPage[InboxItem]:
    return inbox.worst_first(filters)


def get_exception(exception_id: UUID, inbox: InboxQuery) -> InboxItem:
    item = inbox.find(exception_id)
    if item is None:
        raise NotFoundError("exception not found")
    return item
