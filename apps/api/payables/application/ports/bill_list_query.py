from typing import Protocol

from payables.application.read.bill_list_item import BillListItem


class BillListQuery(Protocol):
    def latest(self) -> list[BillListItem]: ...
