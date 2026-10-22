"""The demo data: two tenants, and bills that raise each of the five rules (D55)."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid5

from django.core.management.base import BaseCommand
from django.db import connections

from payables.adapters.orm.bills import BillOrmRepository
from payables.adapters.orm.checks import CheckedBillOrmRepository, CheckJobOrmRepository
from payables.adapters.orm.outbox import OutboxOrmRepository
from payables.adapters.orm.purchase_orders import PurchaseOrderOrmRepository
from payables.adapters.orm.suppliers import SupplierOrmRepository
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.bills import IngestBillCommand, ingest_bill
from payables.application.checks import start_bill_check
from payables.application.purchase_orders import AddPurchaseOrderCommand, add_purchase_order
from payables.application.suppliers import register_supplier
from payables.domain.access import Principal, Role
from payables.domain.bills import BillPayload
from payables.domain.purchase_orders import po_number

INSERT_TENANT = """
INSERT INTO tenant (id, name, created_at) VALUES (%s, %s, now())
ON CONFLICT (id) DO NOTHING
"""

DEMO_NAMESPACE = UUID("5eed0000-0000-4000-8000-000000000000")


@dataclass(frozen=True)
class DemoSupplier:
    name: str
    vat_number: str


@dataclass(frozen=True)
class DemoPurchaseOrder:
    po_number: str
    supplier: DemoSupplier
    amount: int


@dataclass(frozen=True)
class DemoTenant:
    id: UUID
    name: str
    clerk: str
    purchase_orders: tuple[DemoPurchaseOrder, ...]
    bills: tuple[BillPayload, ...]


def _bill(
    supplier: DemoSupplier,
    number: str,
    amount: int,
    issue_date: date,
    *,
    vat_amount: int | None,
    currency: str = "GBP",
    po: str | None = None,
    has_receipt: bool = True,
) -> BillPayload:
    return BillPayload(
        supplier_name=supplier.name,
        supplier_vat_number=supplier.vat_number,
        invoice_number=number,
        amount=amount,
        currency=currency,
        vat_amount=vat_amount,
        issue_date=issue_date,
        po_number=po,
        has_receipt=has_receipt,
    )


FRESH_FARMS = DemoSupplier("Fresh Farms Ltd", "GB123456789")
NORTHERN_PACKAGING = DemoSupplier("Northern Packaging Ltd", "GB987654321")
CITY_CLEANING = DemoSupplier("City Cleaning BV", "NL123456789B01")
RIVERSIDE_LOGISTICS = DemoSupplier("Riverside Logistics", "GB444000222")
MILL_LANE = DemoSupplier("Mill Lane Flour Ltd", "GB111222333")
DAIRY_DIRECT = DemoSupplier("Dairy Direct Ltd", "GB222333444")

# The bills are ingested in this order. A repeat rule puts its exception on the later bill.
ACME = DemoTenant(
    id=UUID("11111111-1111-1111-1111-111111111111"),
    name="Acme Foods",
    clerk="c1",
    purchase_orders=(
        DemoPurchaseOrder("PO-100", FRESH_FARMS, 120000),
        DemoPurchaseOrder("PO-200", NORTHERN_PACKAGING, 45000),
    ),
    bills=(
        _bill(FRESH_FARMS, "INV-001", 120000, date(2026, 10, 1), vat_amount=20000, po="PO-100"),
        # duplicate: the same invoice number as INV-001, after normalisation.
        _bill(FRESH_FARMS, "inv 001", 120000, date(2026, 10, 1), vat_amount=20000),
        # possible_duplicate: the same amount as INV-001, 4 days later.
        _bill(FRESH_FARMS, "INV-002", 120000, date(2026, 10, 5), vat_amount=20000),
        # po_mismatch: PO-200 is for 450.00, the bill is for 520.00.
        _bill(
            NORTHERN_PACKAGING, "NP-7001", 52000, date(2026, 10, 3), vat_amount=8667, po="PO-200"
        ),
        _bill(
            NORTHERN_PACKAGING, "NP-7002", 45000, date(2026, 10, 8), vat_amount=7500, po="PO-200"
        ),
        # missing_vat
        _bill(CITY_CLEANING, "CC-300", 36000, date(2026, 10, 4), vat_amount=None, currency="EUR"),
        # missing_receipt
        _bill(
            RIVERSIDE_LOGISTICS,
            "RL-88",
            18000,
            date(2026, 10, 6),
            vat_amount=3000,
            has_receipt=False,
        ),
    ),
)

BETA = DemoTenant(
    id=UUID("22222222-2222-2222-2222-222222222222"),
    name="Beta Bakery",
    clerk="c9",
    purchase_orders=(),
    bills=(
        _bill(MILL_LANE, "ML-500", 64000, date(2026, 10, 2), vat_amount=10667),
        # duplicate
        _bill(MILL_LANE, "ML 500", 64000, date(2026, 10, 2), vat_amount=10667),
        # missing_receipt
        _bill(DAIRY_DIRECT, "DD-41", 23000, date(2026, 10, 7), vat_amount=3833, has_receipt=False),
    ),
)

DEMO_TENANTS = (ACME, BETA)


class Command(BaseCommand):
    help = "Seed the demo tenants, their data and one check each. A second run changes nothing."

    def handle(self, *args, **options) -> None:
        insert_tenants({str(tenant.id): tenant.name for tenant in DEMO_TENANTS})
        for tenant in DEMO_TENANTS:
            seed_tenant(tenant)


def insert_tenants(tenants: dict[str, str]) -> None:
    # Tenants are created outside the product, so the owner role writes them (US1).
    with connections["owner"].cursor() as cursor:
        for tenant_id, name in tenants.items():
            cursor.execute(INSERT_TENANT, [tenant_id, name])


def seed_tenant(tenant: DemoTenant) -> None:
    """Write the tenant's rows through the product's commands, then queue one check (D55)."""
    clerk = Principal(tenant.id, Role.CLERK, tenant.clerk)
    with tenant_transaction(tenant.id):
        for purchase_order in tenant.purchase_orders:
            _add_purchase_order(clerk, purchase_order)
    # One transaction per bill, so the ingest order is the order of the list.
    bill_ids = [
        _ingest(clerk, f"demo-{number}", bill) for number, bill in enumerate(tenant.bills, start=1)
    ]
    with tenant_transaction(tenant.id):
        _start_check(clerk, bill_ids)


def check_job_id(tenant_id: UUID) -> UUID:
    """The id of the tenant's demo check job. A second run finds it and starts no job."""
    return uuid5(DEMO_NAMESPACE, f"{tenant_id}:check")


def _add_purchase_order(clerk: Principal, purchase_order: DemoPurchaseOrder) -> None:
    tenant_id = clerk.tenant_id
    purchase_orders = PurchaseOrderOrmRepository(tenant_id)
    if purchase_orders.find(po_number(purchase_order.po_number).normalised) is not None:
        return
    suppliers = SupplierOrmRepository(tenant_id)
    supplier = purchase_order.supplier
    supplier_id = register_supplier(clerk, supplier.name, supplier.vat_number, suppliers).id
    command = AddPurchaseOrderCommand(
        purchase_order.po_number, supplier_id, purchase_order.amount, "GBP"
    )
    add_purchase_order(clerk, command, suppliers, purchase_orders, OutboxOrmRepository(tenant_id))


def _ingest(clerk: Principal, key: str, bill: BillPayload) -> UUID:
    tenant_id = clerk.tenant_id
    with tenant_transaction(tenant_id):
        return ingest_bill(
            clerk,
            IngestBillCommand(key, bill),
            SupplierOrmRepository(tenant_id),
            BillOrmRepository(tenant_id),
        ).id


def _start_check(clerk: Principal, bill_ids: list[UUID]) -> None:
    tenant_id = clerk.tenant_id
    jobs = CheckJobOrmRepository(tenant_id)
    job_id = check_job_id(tenant_id)
    if jobs.find(job_id) is not None:
        return
    start_bill_check(
        clerk,
        bill_ids,
        CheckedBillOrmRepository(tenant_id),
        jobs,
        OutboxOrmRepository(tenant_id),
        job_id=job_id,
    )
