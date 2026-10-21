from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from payables.application.authorization import require_role
from payables.application.ports.outbox import Outbox
from payables.application.ports.purchase_order_repository import PurchaseOrderRepository
from payables.application.ports.supplier_repository import SupplierRepository
from payables.domain.errors import NotFoundError
from payables.domain.money import Money
from payables.domain.po_number import po_number
from payables.domain.principal import Principal
from payables.domain.purchase_order import PurchaseOrder
from payables.domain.purchase_order_added import PurchaseOrderAdded
from payables.domain.role import Role


@dataclass(frozen=True)
class AddPurchaseOrderCommand:
    po_number: str
    supplier_id: UUID
    amount: Any
    currency: str


def add_purchase_order(
    principal: Principal,
    command: AddPurchaseOrderCommand,
    suppliers: SupplierRepository,
    purchase_orders: PurchaseOrderRepository,
    outbox: Outbox,
) -> PurchaseOrder:
    require_role(principal, Role.CLERK)
    number = po_number(command.po_number)
    amount = Money(command.amount, command.currency)
    if not suppliers.exists(command.supplier_id):
        raise NotFoundError("supplier not found")
    added = purchase_orders.add(command.supplier_id, number, amount)
    # The PO and its event commit together, so a new PO always re-checks its bills (I16, D44).
    outbox.add([PurchaseOrderAdded(uuid4(), principal.tenant_id, number.normalised)])
    return added
