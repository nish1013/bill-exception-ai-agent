from collections.abc import Sequence
from dataclasses import asdict
from uuid import UUID

from payables.adapters.orm.outbox import OutboxRow
from payables.application.ports.outbox import Message


class OutboxOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def add(self, messages: Sequence[Message]) -> None:
        OutboxRow.objects.bulk_create(
            OutboxRow(
                tenant_id=self._tenant_id,
                command=type(message).__name__,
                payload={name: str(value) for name, value in asdict(message).items()},
            )
            for message in messages
        )
