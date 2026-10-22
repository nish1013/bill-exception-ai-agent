import uuid
from uuid import UUID

from django.db import IntegrityError, models, transaction
from django.db.models import Case, IntegerField, Q, QuerySet, Value, When

from payables.adapters.orm.bills import BillRow
from payables.adapters.orm.constraints import violated_constraint
from payables.adapters.orm.tenants import Tenant
from payables.application.exceptions import InboxFilter, InboxItem
from payables.application.pages import ListPage
from payables.domain.access import SYSTEM_ACTOR
from payables.domain.checks.exceptions import (
    PROPOSAL_SYNCED_STATUS,
    PROPOSAL_UNSYNCED_STATUS,
    WORST_FIRST,
    ExceptionStatus,
    IgnoreReason,
    ResolutionKind,
    StoredException,
    kinds_with,
    rules_with,
    severity_of,
    status_of,
)
from payables.domain.checks.rules import Finding, Rule
from payables.domain.errors import ResolutionExistsError
from payables.domain.proposals.proposals import ProposalStatus

FINDING_KEY = "exception_bill_rule_fingerprint_key"
RESOLUTION_KEY = "resolution_pkey"
LIST_LIMIT = 500

USER_ACTOR = Q(actor__regex=r"\S") & ~Q(actor=SYSTEM_ACTOR)

# An ignore records the user and a reason. A system resolve records the system and no reason.
# A proposal resolution records the approver and its proposal (I8).
KIND_FIELDS = (
    (
        Q(kind=ResolutionKind.IGNORE.value, reason__isnull=False, reason__regex=r"\S")
        & USER_ACTOR
        & Q(proposal=None)
    )
    | Q(kind=ResolutionKind.SYSTEM.value, actor=SYSTEM_ACTOR, reason=None, proposal=None)
    | (Q(kind=ResolutionKind.PROPOSAL.value, reason=None, proposal__isnull=False) & USER_ACTOR)
)

FIELDS = (
    "id",
    "bill_id",
    "bill__supplier__name",
    "bill__invoice_number",
    "rule",
    "related_bill_id",
    "created_at",
    "resolution__kind",
    "resolution__actor",
    "resolution__reason",
    "resolution__proposal__status",
)


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
    # The migration adds the key on (tenant_id, proposal_id) (I1, I8).
    proposal = models.ForeignKey(
        "payables.ProposalRow",
        on_delete=models.PROTECT,
        db_constraint=False,
        null=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payables"
        db_table = "resolution"
        constraints = [
            models.CheckConstraint(condition=KIND_FIELDS, name="resolution_kind_fields"),
        ]


class ExceptionOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def add_missing(self, bill_id: UUID, findings: list[Finding]) -> None:
        # A second check of the bill waits on the first one's key, then adds nothing (I6, D5).
        ExceptionRow.objects.bulk_create(
            [
                ExceptionRow(
                    tenant_id=self._tenant_id,
                    bill_id=bill_id,
                    rule=finding.rule.value,
                    fingerprint=finding.fingerprint,
                    related_bill_id=finding.related_bill_id,
                )
                for finding in findings
            ],
            ignore_conflicts=True,
        )

    def on_bill(self, bill_id: UUID) -> list[StoredException]:
        rows = self._rows().filter(bill_id=bill_id).order_by("id")
        return [
            StoredException(
                id=row["id"],
                rule=Rule(row["rule"]),
                fingerprint=row["fingerprint"],
                resolution=_kind(row["resolution__kind"]),
            )
            for row in rows.values("id", "rule", "fingerprint", "resolution__kind")
        ]

    def exists(self, exception_id: UUID) -> bool:
        return self._rows().filter(id=exception_id).exists()

    def resolutions(self, exception_ids: list[UUID]) -> dict[UUID, ResolutionKind | None]:
        rows = self._rows().filter(id__in=exception_ids).values_list("id", "resolution__kind")
        return {exception_id: _kind(kind) for exception_id, kind in rows}

    def bills_with_open(self, rule: Rule, fingerprint: str) -> list[UUID]:
        rows = self._rows().filter(
            rule=rule.value, fingerprint=fingerprint, resolution__isnull=True
        )
        return list(rows.order_by("bill_id").values_list("bill_id", flat=True).distinct())

    def _rows(self):
        return ExceptionRow.objects.filter(tenant_id=self._tenant_id)


class ResolutionOrmRepository:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def ignore(self, exception_id: UUID, actor: str, reason: IgnoreReason) -> None:
        try:
            with transaction.atomic():
                ResolutionRow.objects.create(
                    exception_id=exception_id,
                    tenant_id=self._tenant_id,
                    kind=ResolutionKind.IGNORE.value,
                    actor=actor,
                    reason=reason.text,
                )
        except IntegrityError as error:
            _raise_if_resolved(error)
            raise

    def resolve_by_proposal(self, exception_ids: list[UUID], proposal_id: UUID, actor: str) -> None:
        # One insert in id order, so two approves on the same exceptions never deadlock.
        try:
            with transaction.atomic():
                ResolutionRow.objects.bulk_create(
                    [
                        ResolutionRow(
                            exception_id=exception_id,
                            tenant_id=self._tenant_id,
                            kind=ResolutionKind.PROPOSAL.value,
                            actor=actor,
                            proposal_id=proposal_id,
                        )
                        for exception_id in sorted(exception_ids)
                    ]
                )
        except IntegrityError as error:
            _raise_if_resolved(error)
            raise

    def resolve_by_system(self, exception_ids: list[UUID]) -> None:
        # An ignore or an approve that commits first keeps the exception (I7).
        ResolutionRow.objects.bulk_create(
            [
                ResolutionRow(
                    exception_id=exception_id,
                    tenant_id=self._tenant_id,
                    kind=ResolutionKind.SYSTEM.value,
                    actor=SYSTEM_ACTOR,
                )
                for exception_id in exception_ids
            ],
            ignore_conflicts=True,
        )

    def reopen(self, exception_ids: list[UUID]) -> None:
        ResolutionRow.objects.filter(
            tenant_id=self._tenant_id,
            exception_id__in=exception_ids,
            kind=ResolutionKind.SYSTEM.value,
        ).delete()


class InboxOrmQuery:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    def worst_first(self, filters: InboxFilter) -> ListPage[InboxItem]:
        rows = self._rows()
        if filters.status is not None:
            rows = rows.filter(with_status(filters.status))
        if filters.severity is not None:
            rows = rows.filter(rule__in=[rule.value for rule in rules_with(filters.severity)])
        listed = (
            rows.annotate(severity_rank=_severity_rank())
            .order_by("severity_rank", "-created_at", "-id")
            .values(*FIELDS)[:LIST_LIMIT]
        )
        return ListPage(items=[_item(row) for row in listed], total_count=rows.count())

    def find(self, exception_id: UUID) -> InboxItem | None:
        row = self._rows().filter(id=exception_id).values(*FIELDS).first()
        return None if row is None else _item(row)

    def _rows(self) -> QuerySet[ExceptionRow]:
        return ExceptionRow.objects.filter(tenant_id=self._tenant_id)


def with_status(status: ExceptionStatus) -> Q:
    if status is ExceptionStatus.OPEN:
        return Q(resolution__isnull=True)
    matches = Q(resolution__kind__in=[kind.value for kind in kinds_with(status)])
    by_proposal = Q(resolution__kind=ResolutionKind.PROPOSAL.value)
    synced = Q(resolution__proposal__status=ProposalStatus.SYNCED.value)
    if status is PROPOSAL_SYNCED_STATUS:
        matches |= by_proposal & synced
    if status is PROPOSAL_UNSYNCED_STATUS:
        matches |= by_proposal & ~synced
    return matches


def _kind(value: str | None) -> ResolutionKind | None:
    return None if value is None else ResolutionKind(value)


def _raise_if_resolved(error: IntegrityError) -> None:
    if violated_constraint(error) == RESOLUTION_KEY:
        raise ResolutionExistsError("the exception already has a resolution") from error


def _severity_rank() -> Case:
    return Case(
        *[
            When(rule__in=[rule.value for rule in rules_with(severity)], then=Value(rank))
            for rank, severity in enumerate(WORST_FIRST)
        ],
        default=Value(len(WORST_FIRST)),
        output_field=IntegerField(),
    )


def _item(row: dict) -> InboxItem:
    rule = Rule(row["rule"])
    kind = row["resolution__kind"]
    return InboxItem(
        id=row["id"],
        bill_id=row["bill_id"],
        supplier_name=row["bill__supplier__name"],
        invoice_number=row["bill__invoice_number"],
        rule=rule,
        severity=severity_of(rule),
        status=status_of(
            None if kind is None else ResolutionKind(kind),
            row["resolution__proposal__status"] == ProposalStatus.SYNCED.value,
        ),
        related_bill_id=row["related_bill_id"],
        created_at=row["created_at"],
        resolved_by=row["resolution__actor"],
        reason=row["resolution__reason"],
    )
