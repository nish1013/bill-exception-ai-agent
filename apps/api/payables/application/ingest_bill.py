from dataclasses import dataclass

from payables.application.authorization import require_role
from payables.application.ports.bill_repository import BillRepository
from payables.application.ports.supplier_repository import SupplierRepository
from payables.domain.access import Principal, Role
from payables.domain.bills import BillDraft, BillPayload, IdempotencyKey, StoredBill
from payables.domain.errors import IdempotencyMismatchError


@dataclass(frozen=True)
class IngestBillCommand:
    idempotency_key: str
    bill: BillPayload


def ingest_bill(
    principal: Principal,
    command: IngestBillCommand,
    suppliers: SupplierRepository,
    bills: BillRepository,
) -> StoredBill:
    require_role(principal, Role.CLERK)
    key = IdempotencyKey(command.idempotency_key)
    draft = BillDraft.parse(command.bill)
    payload_hash = command.bill.digest()

    stored = bills.find_by_key(key)
    if stored is None:
        supplier = suppliers.find_or_add(draft.supplier)
        stored = bills.add_or_find(supplier.id, key, payload_hash, draft)
    if stored.payload_hash != payload_hash:
        raise IdempotencyMismatchError("this idempotency key was used with another payload")
    return stored
