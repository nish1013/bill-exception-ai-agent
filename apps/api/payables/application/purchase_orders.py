from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from payables.application.authorization import require_role
from payables.application.outbox import Outbox
from payables.application.suppliers import SupplierRepository
from payables.domain.access import Principal, Role
from payables.domain.errors import NotFoundError
from payables.domain.money import Money
from payables.domain.purchase_orders import PurchaseOrder, PurchaseOrderAdded, po_number
from payables.domain.text import DocumentNumber


class PurchaseOrderRepository(Protocol):
    def add(self, supplier_id: UUID, po_number: DocumentNumber, amount: Money) -> PurchaseOrder: ...

    def find(self, po_number: str) -> PurchaseOrder | None: ...


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
