from django.db import models
from django.db.models import Q

from payables.adapters.orm.bill import BillRow
from payables.adapters.orm.check_job import CheckJobRow
from payables.adapters.orm.tenant import Tenant
from payables.domain.checks.jobs import CheckResult

JOB_BILL_KEY = "check_job_bill_job_bill_key"


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
