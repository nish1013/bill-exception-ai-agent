from datetime import timedelta
from typing import Protocol
from uuid import UUID

from payables.domain.checks.check_job import CheckJob
from payables.domain.checks.check_result import CheckResult


class CheckJobRepository(Protocol):
    def add(self, requested_by: str, bill_ids: list[UUID]) -> CheckJob: ...

    def find(self, job_id: UUID) -> CheckJob | None: ...

    def is_pending(self, job_id: UUID, bill_id: UUID) -> bool: ...

    def lock(self, job_id: UUID) -> CheckJob | None: ...

    def save_result(
        self, job: CheckJob, bill_id: UUID, result: CheckResult, error: str | None
    ) -> None: ...

    def requeue_if_stale(self, job_id: UUID, stale_after: timedelta) -> list[UUID]: ...
