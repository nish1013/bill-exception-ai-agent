from payables.application.ports.inbox_query import InboxQuery
from payables.application.read.inbox_filter import InboxFilter
from payables.application.read.inbox_item import InboxItem
from payables.application.read.list_page import ListPage
from payables.domain.checks.exception_status import ExceptionStatus


def list_exceptions(filters: InboxFilter, inbox: InboxQuery) -> ListPage[InboxItem]:
    # Status is derived on read (D38). With no resolution row, each exception is open.
    if filters.status not in (None, ExceptionStatus.OPEN):
        return ListPage(items=[], total_count=0)
    return inbox.worst_first(filters.severity)
