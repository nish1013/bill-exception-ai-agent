from typing import Protocol
from uuid import UUID

from payables.domain.bills import BillDraft, IdempotencyKey, StoredBill


class BillRepository(Protocol):
    def find_by_key(self, key: IdempotencyKey) -> StoredBill | None: ...

    def add_or_find(
        self,
        supplier_id: UUID,
        key: IdempotencyKey,
        payload_hash: str,
        draft: BillDraft,
    ) -> StoredBill: ...
