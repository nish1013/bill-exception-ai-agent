import uuid
from collections import defaultdict
from datetime import date
from uuid import UUID

from django.db import IntegrityError, connection, models, transaction
from django.db.models import F, Max, Q
from django.db.models.functions import Now

from payables.adapters.orm.bills import BillRow
from payables.adapters.orm.constraints import violated_constraint
from payables.adapters.orm.exceptions import ExceptionRow
from payables.adapters.orm.purchase_orders import PurchaseOrderRow
from payables.adapters.orm.tenants import Tenant
from payables.application.pages import ListPage
from payables.application.proposals import (
    ProposalActionItem,
    ProposalExceptionItem,
    ProposalItem,
)
from payables.domain.checks.rules import Rule
from payables.domain.errors import ForbiddenError
from payables.domain.proposals.agent import (
    DraftOutcome,
    ProposalScope,
    ScopeBill,
    ScopeException,
    ScopePurchaseOrder,
)
from payables.domain.proposals.proposals import (
    APPROVED_STATUSES,
    DAILY_QUOTA,
    ActionKind,
    FailedReason,
    ProposalStatus,
    QuotaSlot,
    RejectReason,
)

QUOTA_KEY = "proposal_tenant_quota_slot_key"
FOUR_EYES = "proposal_four_eyes"
LIST_LIMIT = 500
UTC_TODAY_SQL = "SELECT (now() AT TIME ZONE 'UTC')::date"

BILL_FIELDS = (
    "id",
    "supplier__name",
    "invoice_number",
    "amount_minor",
    "currency",
    "vat_amount_minor",
    "issue_date",
    "po_number",
    "po_number_norm",
    "has_receipt",
)


class ProposalRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    requested_by = models.TextField()
    status = models.CharField(max_length=16)
    quota_day = models.DateField()
    quota_slot = models.SmallIntegerField()
    failed_reason = models.CharField(max_length=32, null=True)
    approved_by = models.TextField(null=True)
    approved_at = models.DateTimeField(null=True)
    reject_reason = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "payables"
        db_table = "proposal"
        constraints = [
            # Each request takes one slot of the tenant's day. Slot 51 does not exist (I12, D36).
            models.UniqueConstraint(fields=["tenant", "quota_day", "quota_slot"], name=QUOTA_KEY),
            models.CheckConstraint(
                condition=Q(quota_slot__gte=1, quota_slot__lte=DAILY_QUOTA),
                name="proposal_quota_slot_range",
            ),
            models.UniqueConstraint(fields=["tenant", "id"], name="proposal_tenant_id_key"),
            models.CheckConstraint(
                condition=Q(status__in=[status.value for status in ProposalStatus]),
                name="proposal_status_known",
            ),
            models.CheckConstraint(
                condition=Q(
                    status=ProposalStatus.FAILED.value,
                    failed_reason__in=[reason.value for reason in FailedReason],
                )
                | (~Q(status=ProposalStatus.FAILED.value) & Q(failed_reason=None)),
                name="proposal_failed_reason",
            ),
            # The database refuses an approver who is the requester, whatever the caller (I9, D11).
            models.CheckConstraint(condition=~Q(approved_by=F("requested_by")), name=FOUR_EYES),
            models.CheckConstraint(
                condition=Q(
                    status__in=[status.value for status in APPROVED_STATUSES],
                    approved_by__regex=r"\S",
                    approved_at__isnull=False,
                )
                | (
                    ~Q(status__in=[status.value for status in APPROVED_STATUSES])
                    & Q(approved_by=None, approved_at=None)
                ),
                name="proposal_approval_fields",
            ),
            models.CheckConstraint(
                condition=Q(
                    status=ProposalStatus.REJECTED.value,
                    reject_reason__isnull=False,
                    reject_reason__regex=r"\S",
                )
                | (~Q(status=ProposalStatus.REJECTED.value) & Q(reject_reason=None)),
                name="proposal_reject_reason",
            ),
        ]


class ProposalExceptionRow(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    # The migration adds the keys on (tenant_id, proposal_id) and (tenant_id, exception_id) (I1).
    proposal = models.ForeignKey(
        ProposalRow, on_delete=models.PROTECT, db_constraint=False, related_name="exceptions"
    )
    exception = models.ForeignKey(
        ExceptionRow, on_delete=models.PROTECT, db_constraint=False, related_name="+"
    )

    class Meta:
        app_label = "payables"
        db_table = "proposal_exception"
        constraints = [
            models.UniqueConstraint(
                fields=["proposal", "exception"], name="proposal_exception_key"
            ),
        ]


class ProposalActionRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="+")
    # The migration adds the keys on (tenant_id, proposal_id) and (tenant_id, bill_id) (I1).
    proposal = models.ForeignKey(
        ProposalRow, on_delete=models.PROTECT, db_constraint=False, related_name="actions"
    )
    kind = models.CharField(max_length=16)
    bill = models.ForeignKey(
        BillRow, on_delete=models.PROTECT, db_constraint=False, related_name="+"
    )
    po_number = models.TextField(null=True)
    # One sync key for each action. It never changes (I10, D8).
    sync_key = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "proposal_action"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind=ActionKind.MATCH.value, po_number__isnull=False)
                | Q(kind__in=[ActionKind.HOLD.value, ActionKind.CREDIT.value], po_number=None),
                name="proposal_action_kind_fields",
            ),
        ]


class ProposalOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def add(self, requested_by: str, exception_ids: list[UUID]) -> UUID:
        proposal_id = self._take_slot(requested_by)
        ProposalExceptionRow.objects.bulk_create(
            ProposalExceptionRow(
                tenant_id=self._tenant_id, proposal_id=proposal_id, exception_id=exception_id
            )
            for exception_id in exception_ids
        )
        return proposal_id

    def draft_scope(self, proposal_id: UUID) -> ProposalScope | None:
        drafting = self._rows().filter(id=proposal_id, status=ProposalStatus.DRAFTING.value)
        if not drafting.exists():
            return None
        rows = ProposalExceptionRow.objects.filter(
            tenant_id=self._tenant_id, proposal_id=proposal_id
        ).order_by("exception_id")
        exceptions = [
            ScopeException(
                row["exception_id"],
                row["exception__rule"],
                row["exception__bill_id"],
                row["exception__related_bill_id"],
            )
            for row in rows.values(
                "exception_id",
                "exception__rule",
                "exception__bill_id",
                "exception__related_bill_id",
            )
        ]
        bill_ids = {e.bill_id for e in exceptions} | {
            e.related_bill_id for e in exceptions if e.related_bill_id is not None
        }
        bill_rows = list(
            BillRow.objects.filter(tenant_id=self._tenant_id, id__in=bill_ids).values(*BILL_FIELDS)
        )
        return ProposalScope(
            proposal_id=proposal_id,
            exceptions=exceptions,
            bills={row["id"]: _scope_bill(row) for row in bill_rows},
            purchase_orders=self._purchase_orders({row["po_number_norm"] for row in bill_rows}),
        )

    def finish_draft(self, proposal_id: UUID, outcome: DraftOutcome) -> ProposalStatus | None:
        status = ProposalStatus.PENDING if outcome.failed_reason is None else ProposalStatus.FAILED
        reason = None if outcome.failed_reason is None else outcome.failed_reason.value
        # Only the first run that ends writes a result. A repeat finds it pending or failed (D42).
        changed = self._rows().filter(id=proposal_id, status=ProposalStatus.DRAFTING.value)
        if not changed.update(status=status.value, failed_reason=reason, updated_at=Now()):
            return None
        ProposalActionRow.objects.bulk_create(
            ProposalActionRow(
                tenant_id=self._tenant_id,
                proposal_id=proposal_id,
                kind=action.kind.value,
                bill_id=action.bill_id,
                po_number=action.po_number,
            )
            for action in outcome.actions
        )
        return status

    def lock_requester(self, proposal_id: UUID) -> str | None:
        # Each proposal write starts with a lock on the root (D40). Concurrent writes queue here.
        row = self._rows().select_for_update().filter(id=proposal_id).values("requested_by")
        found = row.first()
        return None if found is None else found["requested_by"]

    def approve(self, proposal_id: UUID, approver: str) -> list[UUID] | None:
        # Only a pending proposal takes an approval, so one approve wins (I9, D8).
        pending = self._rows().filter(id=proposal_id, status=ProposalStatus.PENDING.value)
        try:
            with transaction.atomic():
                changed = pending.update(
                    status=ProposalStatus.APPROVED.value,
                    approved_by=approver,
                    approved_at=Now(),
                    updated_at=Now(),
                )
        except IntegrityError as error:
            if violated_constraint(error) == FOUR_EYES:
                raise ForbiddenError(
                    "an approver cannot approve a proposal they requested"
                ) from error
            raise
        if not changed:
            return None
        return self._exception_ids(proposal_id)

    def reject(self, proposal_id: UUID, reason: RejectReason) -> bool:
        pending = self._rows().filter(id=proposal_id, status=ProposalStatus.PENDING.value)
        changed = pending.update(
            status=ProposalStatus.REJECTED.value, reject_reason=reason.text, updated_at=Now()
        )
        return bool(changed)

    def mark_stale(self, proposal_id: UUID) -> list[UUID] | None:
        pending = self._rows().filter(id=proposal_id, status=ProposalStatus.PENDING.value)
        if not pending.update(status=ProposalStatus.STALE.value, updated_at=Now()):
            return None
        return self._exception_ids(proposal_id)

    def _exception_ids(self, proposal_id: UUID) -> list[UUID]:
        rows = ProposalExceptionRow.objects.filter(
            tenant_id=self._tenant_id, proposal_id=proposal_id
        )
        return list(rows.order_by("exception_id").values_list("exception_id", flat=True))

    def _take_slot(self, requested_by: str) -> UUID:
        day = _utc_today()
        for _ in range(DAILY_QUOTA):
            slot = QuotaSlot.after(self._highest_slot(day))
            try:
                with transaction.atomic():
                    row = ProposalRow.objects.create(
                        tenant_id=self._tenant_id,
                        requested_by=requested_by,
                        status=ProposalStatus.DRAFTING.value,
                        quota_day=day,
                        quota_slot=slot.number,
                    )
            except IntegrityError as error:
                # Another request took this slot first. This one takes the next slot (D36).
                if violated_constraint(error) != QUOTA_KEY:
                    raise
                continue
            return row.id
        raise RuntimeError("no quota slot after each slot of the day was tried")

    def _highest_slot(self, day: date) -> int:
        taken = self._rows().filter(quota_day=day).aggregate(highest=Max("quota_slot"))
        return taken["highest"] or 0

    def _purchase_orders(self, numbers: set[str | None]) -> dict[str, ScopePurchaseOrder]:
        rows = PurchaseOrderRow.objects.filter(
            tenant_id=self._tenant_id, po_number_norm__in=[n for n in numbers if n is not None]
        ).values("po_number", "po_number_norm", "amount_minor", "currency")
        return {
            row["po_number_norm"]: ScopePurchaseOrder(
                row["po_number"], row["amount_minor"], row["currency"]
            )
            for row in rows
        }

    def _rows(self):
        return ProposalRow.objects.filter(tenant_id=self._tenant_id)


class ProposalOrmQuery:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def find(self, proposal_id: UUID) -> ProposalItem | None:
        items = self._items(self._rows().filter(id=proposal_id))
        return items[0] if items else None

    def latest(self, status: ProposalStatus | None) -> ListPage[ProposalItem]:
        rows = self._rows()
        if status is not None:
            rows = rows.filter(status=status.value)
        listed = rows.order_by("-created_at", "-id")[:LIST_LIMIT]
        return ListPage(items=self._items(listed), total_count=rows.count())

    def _items(self, rows) -> list[ProposalItem]:
        proposals = list(
            rows.values(
                "id",
                "status",
                "requested_by",
                "quota_slot",
                "failed_reason",
                "approved_by",
                "approved_at",
                "reject_reason",
                "created_at",
            )
        )
        ids = [row["id"] for row in proposals]
        exceptions: dict[UUID, list[ProposalExceptionItem]] = defaultdict(list)
        for row in (
            ProposalExceptionRow.objects.filter(tenant_id=self._tenant_id, proposal_id__in=ids)
            .order_by("exception_id")
            .values(
                "proposal_id", "exception_id", "exception__rule", "exception__bill__invoice_number"
            )
        ):
            exceptions[row["proposal_id"]].append(_exception_item(row))
        actions: dict[UUID, list[ProposalActionItem]] = defaultdict(list)
        for row in (
            ProposalActionRow.objects.filter(tenant_id=self._tenant_id, proposal_id__in=ids)
            .order_by("created_at", "id")
            .values(
                "proposal_id",
                "kind",
                "bill_id",
                "bill__supplier__name",
                "bill__invoice_number",
                "po_number",
            )
        ):
            actions[row["proposal_id"]].append(_action_item(row))
        return [
            ProposalItem(
                id=row["id"],
                status=ProposalStatus(row["status"]),
                requested_by=row["requested_by"],
                quota_slot=row["quota_slot"],
                failed_reason=_failed_reason(row["failed_reason"]),
                approved_by=row["approved_by"],
                approved_at=row["approved_at"],
                reject_reason=row["reject_reason"],
                created_at=row["created_at"],
                exceptions=exceptions[row["id"]],
                actions=actions[row["id"]],
            )
            for row in proposals
        ]

    def _rows(self):
        return ProposalRow.objects.filter(tenant_id=self._tenant_id)


def _utc_today() -> date:
    # The database clock sets the quota day, so each API process counts the same UTC day.
    with connection.cursor() as cursor:
        cursor.execute(UTC_TODAY_SQL)
        return cursor.fetchone()[0]


def _scope_bill(row: dict) -> ScopeBill:
    return ScopeBill(
        id=row["id"],
        supplier_name=row["supplier__name"],
        invoice_number=row["invoice_number"],
        amount_minor=row["amount_minor"],
        currency=row["currency"],
        vat_amount_minor=row["vat_amount_minor"],
        issue_date=row["issue_date"],
        po_number=row["po_number"],
        has_receipt=row["has_receipt"],
    )


def _exception_item(row: dict) -> ProposalExceptionItem:
    return ProposalExceptionItem(
        id=row["exception_id"],
        rule=Rule(row["exception__rule"]),
        invoice_number=row["exception__bill__invoice_number"],
    )


def _action_item(row: dict) -> ProposalActionItem:
    return ProposalActionItem(
        kind=ActionKind(row["kind"]),
        bill_id=row["bill_id"],
        supplier_name=row["bill__supplier__name"],
        invoice_number=row["bill__invoice_number"],
        po_number=row["po_number"],
    )


def _failed_reason(value: str | None) -> FailedReason | None:
    return None if value is None else FailedReason(value)
