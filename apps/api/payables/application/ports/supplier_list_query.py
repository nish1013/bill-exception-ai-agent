from typing import Protocol

from payables.application.read.list_page import ListPage
from payables.domain.suppliers import Supplier


class SupplierListQuery(Protocol):
    def by_name(self) -> ListPage[Supplier]: ...
