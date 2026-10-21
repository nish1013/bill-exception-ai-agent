from collections.abc import Sequence
from dataclasses import asdict
from uuid import UUID

from payables.adapters.orm.outbox import OutboxRow
from payables.domain.checks.check_bill_command import CheckBill


class OutboxOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def add(self, commands: Sequence[CheckBill]) -> None:
        OutboxRow.objects.bulk_create(
            OutboxRow(
                tenant_id=self._tenant_id,
                command=type(command).__name__,
                payload={name: str(value) for name, value in asdict(command).items()},
            )
            for command in commands
        )
