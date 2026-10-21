from payables.application.authorization import require_role
from payables.application.ports.supplier_repository import SupplierRepository
from payables.domain.principal import Principal
from payables.domain.role import Role
from payables.domain.supplier import Supplier
from payables.domain.supplier_identity import SupplierIdentity


def register_supplier(
    principal: Principal, name: str, vat_number: str | None, suppliers: SupplierRepository
) -> Supplier:
    require_role(principal, Role.CLERK)
    return suppliers.find_or_add(SupplierIdentity.parse(name, vat_number))
