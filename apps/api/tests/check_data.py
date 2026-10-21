from dataclasses import replace
from uuid import UUID

from django.db import connections

from payables.adapters.orm.bills import BillOrmRepository
from payables.adapters.orm.checks import CheckedBillOrmRepository, CheckJobOrmRepository
from payables.adapters.orm.exceptions import ExceptionOrmRepository, ResolutionOrmRepository
from payables.adapters.orm.outbox import OutboxOrmRepository
from payables.adapters.orm.purchase_orders import PurchaseOrderOrmRepository
from payables.adapters.orm.suppliers import SupplierOrmRepository
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.bills import IngestBillCommand, ingest_bill
from payables.application.checks import check_bill, record_check_result, start_bill_check
from payables.application.purchase_orders import AddPurchaseOrderCommand, add_purchase_order
from payables.domain.access import Principal, Role
from payables.domain.checks.jobs import CheckBill, CheckJob, CheckResult
from payables.domain.money import Money
from payables.domain.purchase_orders import po_number
from payables.domain.suppliers import SupplierIdentity
from tests.concurrency import owner_count
from tests.ingest_data import B1_PAYLOAD
from tests.tenants import T1, T2

C1 = Principal(T1, Role.CLERK, "c1")
C9 = Principal(T2, Role.CLERK, "c9")
CLERKS = {T1: C1, T2: C9}


def add_bill(key: str, tenant_id: UUID = T1, **changes) -> UUID:
    payload = replace(B1_PAYLOAD, **changes)
    with tenant_transaction(tenant_id):
        stored = ingest_bill(
            CLERKS[tenant_id],
            IngestBillCommand(key, payload),
            SupplierOrmRepository(tenant_id),
            BillOrmRepository(tenant_id),
        )
    return stored.id


def add_po(
    number: str = "PO-100",
    amount: int = 120000,
    currency: str = "GBP",
    supplier: SupplierIdentity | None = None,
    tenant_id: UUID = T1,
) -> UUID:
    identity = supplier or SupplierIdentity.parse(
        B1_PAYLOAD.supplier_name, B1_PAYLOAD.supplier_vat_number
    )
    with tenant_transaction(tenant_id):
        supplier_id = SupplierOrmRepository(tenant_id).find_or_add(identity).id
        return add_purchase_order(
            CLERKS[tenant_id],
            AddPurchaseOrderCommand(number, supplier_id, amount, currency),
            SupplierOrmRepository(tenant_id),
            PurchaseOrderOrmRepository(tenant_id),
            OutboxOrmRepository(tenant_id),
        ).id


def seed_po(number: str = "PO-100", amount: int = 120000) -> UUID:
    identity = SupplierIdentity.parse(B1_PAYLOAD.supplier_name, B1_PAYLOAD.supplier_vat_number)
    with tenant_transaction(T1):
        supplier_id = SupplierOrmRepository(T1).find_or_add(identity).id
        return (
            PurchaseOrderOrmRepository(T1)
            .add(supplier_id, po_number(number), Money(amount, "GBP"))
            .id
        )


def start_job(bill_ids: list[UUID], tenant_id: UUID = T1) -> CheckJob:
    with tenant_transaction(tenant_id):
        return start_bill_check(
            CLERKS[tenant_id],
            bill_ids,
            CheckedBillOrmRepository(tenant_id),
            CheckJobOrmRepository(tenant_id),
            OutboxOrmRepository(tenant_id),
        )


def check(job_id: UUID, bill_id: UUID, tenant_id: UUID = T1) -> None:
    check_in_transaction(job_id, bill_id, tenant_id)()


def check_in_transaction(job_id: UUID, bill_id: UUID, tenant_id: UUID = T1):
    def call() -> None:
        with tenant_transaction(tenant_id):
            check_bill(
                CheckBill(tenant_id, job_id, bill_id),
                CheckedBillOrmRepository(tenant_id),
                PurchaseOrderOrmRepository(tenant_id),
                ExceptionOrmRepository(tenant_id),
                ResolutionOrmRepository(tenant_id),
                CheckJobOrmRepository(tenant_id),
            )

    return call


def fail(job_id: UUID, bill_id: UUID, tenant_id: UUID = T1) -> None:
    with tenant_transaction(tenant_id):
        record_check_result(
            CheckBill(tenant_id, job_id, bill_id),
            CheckResult.FAILED,
            "RuntimeError",
            CheckJobOrmRepository(tenant_id),
        )


def job_row(job_id: UUID) -> tuple[str, int]:
    with connections["owner"].cursor() as cursor:
        cursor.execute("SELECT status FROM check_job WHERE id = %s", [job_id])
        status = cursor.fetchone()[0]
    failed = owner_count("check_job_bill", "job_id = %s AND result = 'failed'", [job_id])
    return status, failed


def exceptions_on(bill_id: UUID) -> list[tuple[str, UUID | None]]:
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            "SELECT rule, related_bill_id FROM exception WHERE bill_id = %s ORDER BY rule",
            [bill_id],
        )
        return list(cursor.fetchall())


def exception_id(bill_id: UUID, rule: str) -> UUID:
    with connections["owner"].cursor() as cursor:
        cursor.execute("SELECT id FROM exception WHERE bill_id = %s AND rule = %s", [bill_id, rule])
        return cursor.fetchone()[0]


PLANT_RESOLUTION = """
INSERT INTO resolution (exception_id, tenant_id, kind, actor, reason, created_at)
SELECT id, tenant_id, %s, %s, %s, now() FROM exception WHERE id = %s
"""


def plant_resolution(exception: UUID, kind: str, actor: str, reason: str | None) -> None:
    with connections["owner"].cursor() as cursor:
        cursor.execute(PLANT_RESOLUTION, [kind, actor, reason, exception])


def resolutions_of(exception: UUID) -> list[tuple[str, str, str | None]]:
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            "SELECT kind, actor, reason FROM resolution WHERE exception_id = %s", [exception]
        )
        return list(cursor.fetchall())
