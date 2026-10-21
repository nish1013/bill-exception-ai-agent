from typing import Protocol
from uuid import UUID

from payables.domain.suppliers import Supplier, SupplierIdentity


class SupplierRepository(Protocol):
    def find_or_add(self, identity: SupplierIdentity) -> Supplier: ...

    def exists(self, supplier_id: UUID) -> bool: ...
