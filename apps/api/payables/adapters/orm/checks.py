import uuid
from datetime import timedelta
from uuid import UUID, uuid4

from django.db import models
from django.db.models import Count, DateTimeField, ExpressionWrapper, Q, QuerySet, Value
from django.db.models.functions import Now

from payables.adapters.orm.bills import BillRow
from payables.adapters.orm.row_level_security import RELAY_ALIAS
from payables.adapters.orm.tenants import Tenant
from payables.domain.checks.jobs import CheckJob, CheckJobStatus, CheckResult
from payables.domain.checks.rules import POSSIBLE_DUPLICATE_WINDOW_DAYS, CheckedBill
from payables.domain.errors import NotFoundError
from payables.domain.money import Money

JOB_BILL_KEY = "check_job_bill_job_bill_key"

FIELDS = (
    "id",
    "supplier_id",
    "invoice_number_norm",
    "amount_minor",
    "currency",
    "issue_date",
    "created_at",
    "vat_amount_minor",
    "has_receipt",
    "po_number_norm",
)


class CheckJobRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    requested_by = models.TextField()
    status = models.CharField(max_length=16)
    bill_count = models.IntegerField()
    enqueued_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "payables"
        db_table = "check_job"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "id"], name="check_job_tenant_id_key"),
            models.CheckConstraint(
                condition=Q(status__in=[status.value for status in CheckJobStatus]),
                name="check_job_status_known",
            ),
            models.CheckConstraint(condition=Q(bill_count__gte=1), name="check_job_has_bills"),
        ]
        indexes = [
            models.Index(
                fields=["enqueued_at"],
                condition=Q(status=CheckJobStatus.QUEUED.value),
                name="check_job_queued_idx",
            )
        ]


class CheckJobBillRow(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    # The migration adds the keys on (tenant_id, job_id) and (tenant_id, bill_id) (I1).
    job = models.ForeignKey(
        CheckJobRow, on_delete=models.PROTECT, db_constraint=False, related_name="+"
    )
    bill = models.ForeignKey(
        BillRow, on_delete=models.PROTECT, db_constraint=False, related_name="+"
    )
    result = models.CharField(max_length=16)
    error = models.TextField(null=True)

    class Meta:
        app_label = "payables"
        db_table = "check_job_bill"
        constraints = [
            models.UniqueConstraint(fields=["job", "bill"], name=JOB_BILL_KEY),
            models.CheckConstraint(
                condition=Q(result__in=[result.value for result in CheckResult]),
                name="check_job_bill_result_known",
            ),
        ]


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


class CheckedBillOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def existing_ids(self, bill_ids: list[UUID]) -> set[UUID]:
        return set(self._rows().filter(id__in=bill_ids).values_list("id", flat=True))

    def get(self, bill_id: UUID) -> CheckedBill:
        row = self._rows().filter(id=bill_id).values(*FIELDS).first()
        if row is None:
            raise NotFoundError("bill not found")
        return _checked_bill(row)

    def earlier_alike(self, bill: CheckedBill) -> list[CheckedBill]:
        window = timedelta(days=POSSIBLE_DUPLICATE_WINDOW_DAYS)
        earlier = Q(created_at__lt=bill.ingested_at) | Q(
            created_at=bill.ingested_at, id__lt=bill.id
        )
        alike = Q(invoice_number_norm=bill.invoice_number) | Q(
            amount_minor=bill.amount.minor_units,
            currency=bill.amount.currency,
            issue_date__range=(bill.issue_date - window, bill.issue_date + window),
        )
        rows = self._rows().filter(earlier, alike, supplier_id=bill.supplier_id).values(*FIELDS)
        return [_checked_bill(row) for row in rows]

    def _rows(self):
        return BillRow.objects.filter(tenant_id=self._tenant_id)


def stale_check_jobs(stale_after: timedelta) -> list[tuple[UUID, UUID]]:
    cutoff = ExpressionWrapper(Now() - Value(stale_after), output_field=DateTimeField())
    rows = CheckJobRow.objects.using(RELAY_ALIAS).filter(
        status=CheckJobStatus.QUEUED.value, enqueued_at__lte=cutoff
    )
    return list(rows.order_by("enqueued_at").values_list("tenant_id", "id"))


def _checked_bill(row: dict) -> CheckedBill:
    return CheckedBill(
        id=row["id"],
        supplier_id=row["supplier_id"],
        invoice_number=row["invoice_number_norm"],
        amount=Money(row["amount_minor"], row["currency"]),
        issue_date=row["issue_date"],
        ingested_at=row["created_at"],
        vat_amount_minor=row["vat_amount_minor"],
        has_receipt=row["has_receipt"],
        po_number=row["po_number_norm"],
    )
