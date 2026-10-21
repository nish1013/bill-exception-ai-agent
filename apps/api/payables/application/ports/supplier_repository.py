from typing import Protocol
from uuid import UUID

from payables.domain.supplier import Supplier
from payables.domain.supplier_identity import SupplierIdentity


class SupplierRepository(Protocol):
    def find_or_add(self, identity: SupplierIdentity) -> Supplier: ...

    def exists(self, supplier_id: UUID) -> bool: ...
