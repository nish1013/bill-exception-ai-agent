import uuid

from django.db import models
from django.db.models import Q

from payables.adapters.orm.bill import BillRow
from payables.adapters.orm.tenant import Tenant
from payables.domain.checks.rule import Rule

FINDING_KEY = "exception_bill_rule_fingerprint_key"


class ExceptionRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    # The migration adds the keys on (tenant_id, bill_id) and (tenant_id, related_bill_id) (I1).
    bill = models.ForeignKey(
        BillRow, on_delete=models.PROTECT, db_constraint=False, related_name="+"
    )
    rule = models.CharField(max_length=32)
    fingerprint = models.TextField()
    related_bill = models.ForeignKey(
        BillRow, on_delete=models.PROTECT, db_constraint=False, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "exception"
        constraints = [
            models.UniqueConstraint(fields=["bill", "rule", "fingerprint"], name=FINDING_KEY),
            models.UniqueConstraint(fields=["tenant", "id"], name="exception_tenant_id_key"),
            models.CheckConstraint(
                condition=Q(rule__in=[rule.value for rule in Rule]), name="exception_rule_known"
            ),
        ]
