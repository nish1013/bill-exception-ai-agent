import uuid

from django.db import models
from django.db.models import Q

from payables.adapters.orm.tenant import Tenant
from payables.domain.checks.jobs import CheckJobStatus


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
