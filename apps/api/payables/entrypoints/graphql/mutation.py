from uuid import UUID

import graphene

from payables.adapters.orm.bill_repository import BillOrmRepository
from payables.adapters.orm.check_job_repository import CheckJobOrmRepository
from payables.adapters.orm.checked_bill_repository import CheckedBillOrmRepository
from payables.adapters.orm.exception_repository import ExceptionOrmRepository
from payables.adapters.orm.inbox_query import InboxOrmQuery
from payables.adapters.orm.outbox_repository import OutboxOrmRepository
from payables.adapters.orm.purchase_order_repository import PurchaseOrderOrmRepository
from payables.adapters.orm.resolution_repository import ResolutionOrmRepository
from payables.adapters.orm.supplier_repository import SupplierOrmRepository
from payables.application.add_purchase_order import AddPurchaseOrderCommand, add_purchase_order
from payables.application.ignore_exception import ignore_exception
from payables.application.ingest_bill import IngestBillCommand, ingest_bill
from payables.application.read.inbox_item import InboxItem
from payables.application.read.list_exceptions import get_exception
from payables.application.register_supplier import register_supplier
from payables.application.start_bill_check import start_bill_check
from payables.domain.bill_payload import BillPayload
from payables.domain.checks.check_job import CheckJob
from payables.domain.principal import Principal
from payables.domain.purchase_order import PurchaseOrder
from payables.domain.supplier import Supplier
from payables.entrypoints.graphql.bill_input import BillInput
from payables.entrypoints.graphql.check_job_type import CheckJobType
from payables.entrypoints.graphql.exception_type import ExceptionType
from payables.entrypoints.graphql.ingest_bill_payload import IngestBillPayload
from payables.entrypoints.graphql.minor_units import MinorUnits
from payables.entrypoints.graphql.purchase_order_type import PurchaseOrderType
from payables.entrypoints.graphql.supplier_type import SupplierType


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
