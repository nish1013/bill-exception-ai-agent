from uuid import UUID

import graphene
from django.db import transaction

from payables.adapters.orm.accounting import StubLedgerOrmQuery
from payables.adapters.orm.audit import AuditOrmLog
from payables.adapters.orm.bills import BillListOrmQuery, BillOrmRepository
from payables.adapters.orm.checks import CheckedBillOrmRepository, CheckJobOrmRepository
from payables.adapters.orm.exceptions import (
    ExceptionOrmRepository,
    InboxOrmQuery,
    ResolutionOrmRepository,
)
from payables.adapters.orm.outbox import OutboxOrmRepository
from payables.adapters.orm.proposals import (
    ProposalOrmQuery,
    ProposalOrmRepository,
    ProposalSyncOrmRepository,
)
from payables.adapters.orm.purchase_orders import PurchaseOrderOrmRepository
from payables.adapters.orm.suppliers import SupplierListOrmQuery, SupplierOrmRepository
from payables.adapters.orm.tenants import TenantRepository
from payables.adapters.rate_limit import RedisProposalRateLimiter
from payables.application.bills import BillListItem, IngestBillCommand, ingest_bill
from payables.application.checks import get_check_job, start_bill_check
from payables.application.exceptions import (
    InboxFilter,
    InboxItem,
    get_exception,
    ignore_exception,
    list_exceptions,
)
from payables.application.pages import ListPage
from payables.application.proposals import (
    ProposalItem,
    approve_fix_proposal,
    get_proposal,
    list_proposals,
    reject_fix_proposal,
    request_fix_proposal,
)
from payables.application.purchase_orders import AddPurchaseOrderCommand, add_purchase_order
from payables.application.suppliers import register_supplier
from payables.application.sync import LedgerEntry, list_ledger, retry_sync
from payables.domain.access import Principal
from payables.domain.bills import BillPayload
from payables.domain.checks.jobs import CheckJob
from payables.domain.purchase_orders import PurchaseOrder
from payables.domain.suppliers import Supplier
from payables.entrypoints.graphql.accounting import LedgerListType
from payables.entrypoints.graphql.bills import BillInput, BillListType, IngestBillPayload
from payables.entrypoints.graphql.checks import CheckJobType
from payables.entrypoints.graphql.exceptions import ExceptionListType, ExceptionType
from payables.entrypoints.graphql.proposals import ProposalListType, ProposalType
from payables.entrypoints.graphql.purchase_orders import PurchaseOrderType
from payables.entrypoints.graphql.scalars import MinorUnits
from payables.entrypoints.graphql.suppliers import SupplierListType, SupplierType
from payables.entrypoints.graphql.viewer import Viewer


class Query(graphene.ObjectType):
    viewer = graphene.Field(Viewer, required=True)
    bills = graphene.Field(BillListType, required=True)
    suppliers = graphene.Field(SupplierListType, required=True)
    exceptions = graphene.Field(
        ExceptionListType,
        required=True,
        status=graphene.String(),
        severity=graphene.String(),
    )
    check_job = graphene.Field(CheckJobType, required=True, id=graphene.UUID(required=True))
    proposals = graphene.Field(ProposalListType, required=True, status=graphene.String())
    proposal = graphene.Field(ProposalType, required=True, id=graphene.UUID(required=True))
    accounting_ledger = graphene.Field(LedgerListType, required=True)

    def resolve_viewer(root, info) -> Viewer:
        principal = _principal(info)
        return Viewer(
            tenant_id=principal.tenant_id,
            tenant_name=TenantRepository().find_name(principal.tenant_id),
            role=principal.role.value,
        )

    def resolve_bills(root, info) -> ListPage[BillListItem]:
        return BillListOrmQuery(_principal(info).tenant_id).latest()

    def resolve_suppliers(root, info) -> ListPage[Supplier]:
        return SupplierListOrmQuery(_principal(info).tenant_id).by_name()

    def resolve_exceptions(
        root, info, status: str | None = None, severity: str | None = None
    ) -> ListPage[InboxItem]:
        inbox = InboxOrmQuery(_principal(info).tenant_id)
        return list_exceptions(InboxFilter.parse(status, severity), inbox)

    def resolve_check_job(root, info, id: UUID) -> CheckJob:
        return get_check_job(id, CheckJobOrmRepository(_principal(info).tenant_id))

    def resolve_proposals(root, info, status: str | None = None) -> ListPage[ProposalItem]:
        return list_proposals(status, ProposalOrmQuery(_principal(info).tenant_id))

    def resolve_proposal(root, info, id: UUID) -> ProposalItem:
        return get_proposal(id, ProposalOrmQuery(_principal(info).tenant_id))

    def resolve_accounting_ledger(root, info) -> ListPage[LedgerEntry]:
        return list_ledger(StubLedgerOrmQuery(_principal(info).tenant_id))


class Mutation(graphene.ObjectType):
    register_supplier = graphene.Field(
        SupplierType,
        required=True,
        name=graphene.String(required=True),
        vat_number=graphene.String(),
    )
    add_purchase_order = graphene.Field(
        PurchaseOrderType,
        required=True,
        po_number=graphene.String(required=True),
        supplier_id=graphene.UUID(required=True),
        amount=MinorUnits(required=True),
        currency=graphene.String(required=True),
    )
    ingest_bill = graphene.Field(
        IngestBillPayload,
        required=True,
        idempotency_key=graphene.String(required=True),
        bill=BillInput(required=True),
    )
    start_bill_check = graphene.Field(
        CheckJobType,
        required=True,
        bill_ids=graphene.List(graphene.NonNull(graphene.UUID), required=True),
    )
    ignore_exception = graphene.Field(
        ExceptionType,
        required=True,
        exception_id=graphene.UUID(required=True),
        reason=graphene.String(required=True),
    )
    request_fix_proposal = graphene.Field(
        ProposalType,
        required=True,
        exception_ids=graphene.List(graphene.NonNull(graphene.UUID), required=True),
    )
    approve_fix_proposal = graphene.Field(
        ProposalType, required=True, proposal_id=graphene.UUID(required=True)
    )
    reject_fix_proposal = graphene.Field(
        ProposalType,
        required=True,
        proposal_id=graphene.UUID(required=True),
        reason=graphene.String(required=True),
    )
    retry_sync = graphene.Field(
        ProposalType, required=True, proposal_id=graphene.UUID(required=True)
    )

    def resolve_register_supplier(root, info, name: str, vat_number: str | None = None) -> Supplier:
        principal = _principal(info)
        return register_supplier(
            principal, name, vat_number, SupplierOrmRepository(principal.tenant_id)
        )

    def resolve_add_purchase_order(
        root, info, po_number: str, supplier_id: UUID, amount, currency: str
    ) -> PurchaseOrder:
        principal = _principal(info)
        command = AddPurchaseOrderCommand(po_number, supplier_id, amount, currency)
        return add_purchase_order(
            principal,
            command,
            SupplierOrmRepository(principal.tenant_id),
            PurchaseOrderOrmRepository(principal.tenant_id),
            OutboxOrmRepository(principal.tenant_id),
        )

    def resolve_ingest_bill(root, info, idempotency_key: str, bill: BillInput) -> IngestBillPayload:
        principal = _principal(info)
        command = IngestBillCommand(idempotency_key, _bill_payload(bill))
        stored = ingest_bill(
            principal,
            command,
            SupplierOrmRepository(principal.tenant_id),
            BillOrmRepository(principal.tenant_id),
        )
        return IngestBillPayload(bill_id=stored.id, supplier_id=stored.supplier_id)

    def resolve_start_bill_check(root, info, bill_ids: list[UUID]) -> CheckJob:
        principal = _principal(info)
        tenant_id = principal.tenant_id
        return start_bill_check(
            principal,
            bill_ids,
            CheckedBillOrmRepository(tenant_id),
            CheckJobOrmRepository(tenant_id),
            OutboxOrmRepository(tenant_id),
        )

    def resolve_ignore_exception(root, info, exception_id: UUID, reason: str) -> InboxItem:
        principal = _principal(info)
        tenant_id = principal.tenant_id
        ignore_exception(
            principal,
            exception_id,
            reason,
            ExceptionOrmRepository(tenant_id),
            ResolutionOrmRepository(tenant_id),
        )
        return get_exception(exception_id, InboxOrmQuery(tenant_id))

    def resolve_request_fix_proposal(root, info, exception_ids: list[UUID]) -> ProposalItem:
        principal = _principal(info)
        tenant_id = principal.tenant_id
        proposal_id = request_fix_proposal(
            principal,
            exception_ids,
            RedisProposalRateLimiter(),
            ExceptionOrmRepository(tenant_id),
            ProposalOrmRepository(tenant_id),
            OutboxOrmRepository(tenant_id),
        )
        return get_proposal(proposal_id, ProposalOrmQuery(tenant_id))

    def resolve_approve_fix_proposal(root, info, proposal_id: UUID) -> ProposalItem:
        principal = _principal(info)
        tenant_id = principal.tenant_id
        approve_fix_proposal(
            principal,
            proposal_id,
            ProposalOrmRepository(tenant_id),
            ResolutionOrmRepository(tenant_id),
            AuditOrmLog(tenant_id),
            OutboxOrmRepository(tenant_id),
            transaction.atomic,
        )
        return get_proposal(proposal_id, ProposalOrmQuery(tenant_id))

    def resolve_reject_fix_proposal(root, info, proposal_id: UUID, reason: str) -> ProposalItem:
        principal = _principal(info)
        tenant_id = principal.tenant_id
        reject_fix_proposal(
            principal, proposal_id, reason, ProposalOrmRepository(tenant_id), AuditOrmLog(tenant_id)
        )
        return get_proposal(proposal_id, ProposalOrmQuery(tenant_id))

    def resolve_retry_sync(root, info, proposal_id: UUID) -> ProposalItem:
        principal = _principal(info)
        tenant_id = principal.tenant_id
        retry_sync(
            principal,
            proposal_id,
            ProposalSyncOrmRepository(tenant_id),
            OutboxOrmRepository(tenant_id),
        )
        return get_proposal(proposal_id, ProposalOrmQuery(tenant_id))


def _principal(info) -> Principal:
    return info.context.principal


def _bill_payload(bill: BillInput) -> BillPayload:
    return BillPayload(
        supplier_name=bill.supplier_name,
        supplier_vat_number=bill.get("supplier_vat_number"),
        invoice_number=bill.invoice_number,
        amount=bill.amount,
        currency=bill.currency,
        vat_amount=bill.get("vat_amount"),
        issue_date=bill.issue_date,
        po_number=bill.get("po_number"),
        has_receipt=bill.has_receipt,
    )


schema = graphene.Schema(query=Query, mutation=Mutation)
