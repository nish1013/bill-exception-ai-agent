from typing import Protocol
from uuid import UUID

from payables.application.authorization import require_role
from payables.application.pages import ListPage
from payables.domain.access import Principal, Role
from payables.domain.suppliers import Supplier, SupplierIdentity


class SupplierRepository(Protocol):
    def find_or_add(self, identity: SupplierIdentity) -> Supplier: ...

    def exists(self, supplier_id: UUID) -> bool: ...


class SupplierListQuery(Protocol):
    def by_name(self) -> ListPage[Supplier]: ...


def register_supplier(
    principal: Principal, name: str, vat_number: str | None, suppliers: SupplierRepository
) -> Supplier:
    require_role(principal, Role.CLERK)
    return suppliers.find_or_add(SupplierIdentity.parse(name, vat_number))
