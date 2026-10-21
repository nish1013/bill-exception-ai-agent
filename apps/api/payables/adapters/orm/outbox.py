import uuid
from collections.abc import Sequence
from dataclasses import asdict
from uuid import UUID

from django.db import models
from django.db.models import Q

from payables.adapters.orm.tenants import Tenant
from payables.application.outbox import Message


class OutboxRow(models.Model):
    id = models.BigAutoField(primary_key=True)
    message_id = models.UUIDField(default=uuid.uuid4, unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    command = models.CharField(max_length=64)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True)

    class Meta:
        app_label = "payables"
        db_table = "outbox"
        indexes = [
            models.Index(
                fields=["id"], condition=Q(sent_at__isnull=True), name="outbox_unsent_idx"
            ),
            models.Index(fields=["sent_at"], name="outbox_sent_at_idx"),
        ]


class OutboxOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def add(self, messages: Sequence[Message]) -> None:
        OutboxRow.objects.bulk_create(
            OutboxRow(
                tenant_id=self._tenant_id,
                command=type(message).__name__,
                payload={name: str(value) for name, value in asdict(message).items()},
            )
            for message in messages
        )
