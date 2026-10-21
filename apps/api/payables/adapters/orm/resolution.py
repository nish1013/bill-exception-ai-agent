from django.db import models
from django.db.models import Q

from payables.adapters.orm.exception import ExceptionRow
from payables.adapters.orm.tenant import Tenant
from payables.domain.access import SYSTEM_ACTOR
from payables.domain.checks.exceptions import ResolutionKind

RESOLUTION_KEY = "resolution_pkey"

# An ignore records the user and a reason. A system resolve records the system and no reason (I8).
KIND_FIELDS = (
    Q(kind=ResolutionKind.IGNORE.value, reason__isnull=False, reason__regex=r"\S")
    & Q(actor__regex=r"\S")
    & ~Q(actor=SYSTEM_ACTOR)
) | Q(kind=ResolutionKind.SYSTEM.value, actor=SYSTEM_ACTOR, reason=None)


class ResolutionRow(models.Model):
    # The primary key allows one resolution for each exception (I7). The migration adds the key
    # on (tenant_id, exception_id), so both rows share a tenant (I1).
    exception = models.OneToOneField(
        ExceptionRow,
        primary_key=True,
        on_delete=models.PROTECT,
        db_constraint=False,
        related_name="resolution",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=16)
    actor = models.TextField()
    reason = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "resolution"
        constraints = [
            models.CheckConstraint(condition=KIND_FIELDS, name="resolution_kind_fields"),
        ]
