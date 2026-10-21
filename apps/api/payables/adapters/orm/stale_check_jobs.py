from datetime import timedelta
from uuid import UUID

from django.db.models import DateTimeField, ExpressionWrapper, Value
from django.db.models.functions import Now

from payables.adapters.orm.check_job import CheckJobRow
from payables.adapters.orm.row_level_security import RELAY_ALIAS
from payables.domain.checks.check_job_status import CheckJobStatus


def stale_check_jobs(stale_after: timedelta) -> list[tuple[UUID, UUID]]:
    cutoff = ExpressionWrapper(Now() - Value(stale_after), output_field=DateTimeField())
    rows = CheckJobRow.objects.using(RELAY_ALIAS).filter(
        status=CheckJobStatus.QUEUED.value, enqueued_at__lte=cutoff
    )
    return list(rows.order_by("enqueued_at").values_list("tenant_id", "id"))
