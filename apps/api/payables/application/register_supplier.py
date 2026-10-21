from payables.application.authorization import require_role
from payables.application.ports.supplier_repository import SupplierRepository
from payables.domain.access import Principal, Role
from payables.domain.suppliers import Supplier, SupplierIdentity


def register_supplier(
    principal: Principal, name: str, vat_number: str | None, suppliers: SupplierRepository
) -> Supplier:
    require_role(principal, Role.CLERK)
    return suppliers.find_or_add(SupplierIdentity.parse(name, vat_number))
