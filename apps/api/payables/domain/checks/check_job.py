from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from payables.domain.checks.bill_check_completed import BillCheckCompleted
from payables.domain.checks.bill_check_progress import BillCheckProgress
from payables.domain.checks.check_job_status import CheckJobStatus
from payables.domain.checks.check_result import CheckResult
from payables.domain.errors import ValidationError

MAX_BILLS = 500
QUEUED_STALE_AFTER = timedelta(minutes=5)
DONE_STATUSES = frozenset({CheckJobStatus.COMPLETED, CheckJobStatus.FAILED})


@dataclass
class CheckJob:
    id: UUID
    status: CheckJobStatus
    bill_count: int
    ok_count: int
    failed_count: int

    @staticmethod
    def bills_to_check(bill_ids: Iterable[UUID]) -> list[UUID]:
        unique = list(dict.fromkeys(bill_ids))
        if not unique:
            raise ValidationError("a check needs at least one bill")
        if len(unique) > MAX_BILLS:
            raise ValidationError(f"a check takes at most {MAX_BILLS} bills")
        return unique

    @property
    def pending_count(self) -> int:
        return self.bill_count - self.ok_count - self.failed_count

    @property
    def seq(self) -> int:
        # Each recorded result adds one under the job lock, so seq only goes up (D19).
        return self.ok_count + self.failed_count

    @property
    def percent(self) -> int:
        return self.seq * 100 // self.bill_count

    @property
    def is_done(self) -> bool:
        return self.status in DONE_STATUSES

    def progress_events(self) -> list[BillCheckProgress | BillCheckCompleted]:
        events: list[BillCheckProgress | BillCheckCompleted] = [
            BillCheckProgress(self.id, self.seq, self.percent)
        ]
        if self.is_done:
            events.append(BillCheckCompleted(self.id, self.seq, self.status, self.failed_count))
        return events

    def record(self, result: CheckResult) -> None:
        # The caller holds the job lock, so the counts include every committed result (I13).
        if result is CheckResult.PENDING or self.pending_count == 0:
            raise ValueError(f"job {self.id} cannot record {result} now")
        if result is CheckResult.OK:
            self.ok_count += 1
        else:
            self.failed_count += 1
        self.status = self._status_after_record()

    def _status_after_record(self) -> CheckJobStatus:
        if self.pending_count > 0:
            return CheckJobStatus.RUNNING
        # A job with no good bill gave the clerk nothing (D41).
        return CheckJobStatus.FAILED if self.ok_count == 0 else CheckJobStatus.COMPLETED
