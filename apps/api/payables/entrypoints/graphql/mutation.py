from uuid import UUID

import graphene

from payables.adapters.orm.bill_repository import BillOrmRepository
from payables.adapters.orm.purchase_order_repository import PurchaseOrderOrmRepository
from payables.adapters.orm.supplier_repository import SupplierOrmRepository
from payables.application.add_purchase_order import AddPurchaseOrderCommand, add_purchase_order
from payables.application.ingest_bill import IngestBillCommand, ingest_bill
from payables.application.register_supplier import register_supplier
from payables.domain.bill_payload import BillPayload
from payables.domain.principal import Principal
from payables.domain.purchase_order import PurchaseOrder
from payables.domain.supplier import Supplier
from payables.entrypoints.graphql.bill_input import BillInput
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
