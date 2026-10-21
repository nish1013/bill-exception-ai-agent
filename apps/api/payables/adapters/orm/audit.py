import uuid
from collections.abc import Sequence
from uuid import UUID

from django.db import models

from payables.adapters.orm.proposals import ProposalRow
from payables.adapters.orm.tenants import Tenant
from payables.domain.audit import AuditEntry


class AuditRow(models.Model):
    # The app role can only insert. No path changes or removes a record (I15).
    # The id is set here, so an insert needs no RETURNING and no SELECT grant.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    # The migration adds the key on (tenant_id, proposal_id) (I1).
    proposal = models.ForeignKey(
        ProposalRow, on_delete=models.PROTECT, db_constraint=False, null=True, related_name="+"
    )
    actor = models.TextField()
    kind = models.CharField(max_length=32)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "audit"


class AuditOrmLog:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def add(self, proposal_id: UUID, entries: Sequence[AuditEntry]) -> None:
        AuditRow.objects.bulk_create(
            AuditRow(
                tenant_id=self._tenant_id,
                proposal_id=proposal_id,
                actor=entry.actor,
                kind=entry.kind.value,
                payload=entry.payload,
            )
            for entry in entries
        )
