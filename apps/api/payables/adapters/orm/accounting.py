from uuid import UUID

from django.db import models
from django.db.models import Q

from payables.adapters.orm.tenants import Tenant
from payables.application.pages import ListPage
from payables.application.sync import LedgerEntry
from payables.domain.proposals.proposals import ActionKind
from payables.domain.proposals.sync import SyncAnswer

LIST_LIMIT = 500
STUB_MODES = ("ok", "fail", "callback")


class StubLedgerRow(models.Model):
    """What the demo accounting stub received. It stands in for the books of an outside system."""

    # The stub keeps one row for each sync key, so a repeat send posts nothing new (D8).
    sync_key = models.UUIDField(primary_key=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=16)
    bill_id = models.UUIDField()
    supplier_name = models.TextField()
    invoice_number = models.TextField()
    po_number = models.TextField(null=True)
    answer = models.CharField(max_length=16)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "stub_ledger"
        constraints = [
            models.CheckConstraint(
                condition=Q(answer__in=[answer.value for answer in SyncAnswer]),
                name="stub_ledger_answer_known",
            ),
        ]


class StubModeRow(models.Model):
    """The stub answer for one tenant. A tenant with no row gets ACCOUNTING_STUB_MODE."""

    tenant = models.OneToOneField(
        Tenant, primary_key=True, on_delete=models.PROTECT, related_name="+"
    )
    mode = models.CharField(max_length=16)

    class Meta:
        app_label = "payables"
        db_table = "stub_mode"
        constraints = [
            models.CheckConstraint(condition=Q(mode__in=STUB_MODES), name="stub_mode_known"),
        ]


class StubLedgerOrmQuery:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def latest(self) -> ListPage[LedgerEntry]:
        rows = StubLedgerRow.objects.filter(tenant_id=self._tenant_id)
        listed = rows.order_by("-received_at", "-sync_key")[:LIST_LIMIT]
        return ListPage(
            items=[
                LedgerEntry(
                    sync_key=row.sync_key,
                    kind=ActionKind(row.kind),
                    supplier_name=row.supplier_name,
                    invoice_number=row.invoice_number,
                    po_number=row.po_number,
                    answer=SyncAnswer(row.answer),
                    received_at=row.received_at,
                )
                for row in listed
            ],
            total_count=rows.count(),
        )
