from datetime import timedelta
from uuid import UUID

from django.db.models import DateTimeField, ExpressionWrapper, Value
from django.db.models.functions import Now

from payables.adapters.orm.check_job import CheckJobRow
from payables.domain.checks.check_job_status import CheckJobStatus

# The sweeper finds jobs of all tenants, so it reads as the owner role. Each requeue then runs
# in a tenant transaction as the app role.
OWNER = "owner"


def stale_check_jobs(stale_after: timedelta) -> list[tuple[UUID, UUID]]:
    cutoff = ExpressionWrapper(Now() - Value(stale_after), output_field=DateTimeField())
    rows = CheckJobRow.objects.using(OWNER).filter(
        status=CheckJobStatus.QUEUED.value, enqueued_at__lte=cutoff
    )
    return list(rows.order_by("enqueued_at").values_list("tenant_id", "id"))
