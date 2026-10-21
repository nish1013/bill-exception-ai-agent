from datetime import timedelta
from uuid import UUID, uuid4

from django.db.models import Count, DateTimeField, ExpressionWrapper, QuerySet, Value
from django.db.models.functions import Now

from payables.adapters.orm.check_job import CheckJobRow
from payables.adapters.orm.check_job_bill import CheckJobBillRow
from payables.domain.checks.jobs import CheckJob, CheckJobStatus, CheckResult


class CheckJobOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def add(self, requested_by: str, bill_ids: list[UUID], job_id: UUID | None = None) -> CheckJob:
        row = CheckJobRow.objects.create(
            id=job_id or uuid4(),
            tenant_id=self._tenant_id,
            requested_by=requested_by,
            status=CheckJobStatus.QUEUED.value,
            bill_count=len(bill_ids),
            enqueued_at=Now(),
        )
        CheckJobBillRow.objects.bulk_create(
            CheckJobBillRow(
                tenant_id=self._tenant_id,
                job_id=row.id,
                bill_id=bill_id,
                result=CheckResult.PENDING.value,
            )
            for bill_id in bill_ids
        )
        return CheckJob(row.id, CheckJobStatus.QUEUED, len(bill_ids), ok_count=0, failed_count=0)

    def is_pending(self, job_id: UUID, bill_id: UUID) -> bool:
        return self._bills(job_id).filter(bill_id=bill_id, result=CheckResult.PENDING).exists()

    def find(self, job_id: UUID) -> CheckJob | None:
        return self._load(CheckJobRow.objects.all(), job_id)

    def lock(self, job_id: UUID) -> CheckJob | None:
        # Two workers that finish the last two bills must not both see the other one pending (I13).
        return self._load(CheckJobRow.objects.select_for_update(), job_id)

    def save_result(
        self, job: CheckJob, bill_id: UUID, result: CheckResult, error: str | None
    ) -> None:
        self._bills(job.id).filter(bill_id=bill_id).update(result=result.value, error=error)
        CheckJobRow.objects.filter(tenant_id=self._tenant_id, id=job.id).update(
            status=job.status.value, updated_at=Now()
        )

    def requeue_if_stale(self, job_id: UUID, stale_after: timedelta) -> list[UUID]:
        cutoff = ExpressionWrapper(Now() - Value(stale_after), output_field=DateTimeField())
        claimed = CheckJobRow.objects.filter(
            tenant_id=self._tenant_id,
            id=job_id,
            status=CheckJobStatus.QUEUED.value,
            enqueued_at__lte=cutoff,
        ).update(enqueued_at=Now())
        if not claimed:
            return []
        pending = self._bills(job_id).filter(result=CheckResult.PENDING)
        return list(pending.order_by("id").values_list("bill_id", flat=True))

    def _load(self, rows: QuerySet[CheckJobRow], job_id: UUID) -> CheckJob | None:
        row = (
            rows.filter(tenant_id=self._tenant_id, id=job_id).values("status", "bill_count").first()
        )
        if row is None:
            return None
        counts = dict(
            self._bills(job_id).values_list("result").annotate(count=Count("id")).order_by()
        )
        return CheckJob(
            id=job_id,
            status=CheckJobStatus(row["status"]),
            bill_count=row["bill_count"],
            ok_count=counts.get(CheckResult.OK.value, 0),
            failed_count=counts.get(CheckResult.FAILED.value, 0),
        )

    def _bills(self, job_id: UUID):
        return CheckJobBillRow.objects.filter(tenant_id=self._tenant_id, job_id=job_id)
