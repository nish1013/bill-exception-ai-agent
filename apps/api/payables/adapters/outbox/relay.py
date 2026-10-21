from datetime import timedelta

from django.db import transaction
from django.db.models import DateTimeField, ExpressionWrapper, Value
from django.db.models.functions import Now

from payables.adapters.orm.outbox import OutboxRow
from payables.adapters.orm.row_level_security import RELAY_ALIAS
from payables.adapters.outbox.publisher import Publisher

BATCH_SIZE = 500
KEEP_SENT_FOR = timedelta(days=7)


class OutboxRelay:
    def __init__(self, publisher: Publisher) -> None:
        self._publisher = publisher

    def publish_pending(self) -> int:
        with transaction.atomic(using=RELAY_ALIAS):
            rows = list(
                OutboxRow.objects.using(RELAY_ALIAS)
                .select_for_update(skip_locked=True)
                .filter(sent_at__isnull=True)
                .order_by("id")
                .values("id", "message_id", "command", "payload")[:BATCH_SIZE]
            )
            for row in rows:
                self._publisher.publish(row["message_id"], row["command"], row["payload"])
            # A crash before this commit sends the batch again. Each handler is idempotent (D42).
            OutboxRow.objects.using(RELAY_ALIAS).filter(id__in=[row["id"] for row in rows]).update(
                sent_at=Now()
            )
        return len(rows)

    def delete_sent(self) -> int:
        cutoff = ExpressionWrapper(Now() - Value(KEEP_SENT_FOR), output_field=DateTimeField())
        deleted, _ = OutboxRow.objects.using(RELAY_ALIAS).filter(sent_at__lte=cutoff).delete()
        return deleted
