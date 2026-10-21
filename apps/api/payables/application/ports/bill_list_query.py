from typing import Protocol

from payables.application.read.bill_list_item import BillListItem
from payables.application.read.list_page import ListPage


class BillListQuery(Protocol):
    def latest(self) -> ListPage[BillListItem]: ...
