from uuid import UUID

from django.db import IntegrityError, transaction

from payables.adapters.orm.integrity import violated_constraint
from payables.adapters.orm.resolution import RESOLUTION_KEY, ResolutionRow
from payables.domain.checks.resolution_kind import ResolutionKind
from payables.domain.errors import ConflictError
from payables.domain.ignore_reason import IgnoreReason
from payables.domain.system_actor import SYSTEM_ACTOR


class ResolutionOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def ignore(self, exception_id: UUID, actor: str, reason: IgnoreReason) -> None:
        try:
            with transaction.atomic():
                ResolutionRow.objects.create(
                    exception_id=exception_id,
                    tenant_id=self._tenant_id,
                    kind=ResolutionKind.IGNORE.value,
                    actor=actor,
                    reason=reason.text,
                )
        except IntegrityError as error:
            if violated_constraint(error) == RESOLUTION_KEY:
                raise ConflictError("the exception already has a resolution") from error
            raise

    def resolve_by_system(self, exception_ids: list[UUID]) -> None:
        # An ignore or an approve that commits first keeps the exception (I7).
        ResolutionRow.objects.bulk_create(
            [
                ResolutionRow(
                    exception_id=exception_id,
                    tenant_id=self._tenant_id,
                    kind=ResolutionKind.SYSTEM.value,
                    actor=SYSTEM_ACTOR,
                )
                for exception_id in exception_ids
            ],
            ignore_conflicts=True,
        )

    def reopen(self, exception_ids: list[UUID]) -> None:
        ResolutionRow.objects.filter(
            tenant_id=self._tenant_id,
            exception_id__in=exception_ids,
            kind=ResolutionKind.SYSTEM.value,
        ).delete()
