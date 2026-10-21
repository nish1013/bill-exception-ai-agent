from dataclasses import replace
from uuid import UUID

from django.db import connections

from payables.adapters.orm.bill_repository import BillOrmRepository
from payables.adapters.orm.check_job_repository import CheckJobOrmRepository
from payables.adapters.orm.checked_bill_repository import CheckedBillOrmRepository
from payables.adapters.orm.exception_repository import ExceptionOrmRepository
from payables.adapters.orm.outbox_repository import OutboxOrmRepository
from payables.adapters.orm.supplier_repository import SupplierOrmRepository
from payables.adapters.orm.tenancy import tenant_transaction
from payables.application.check_bill import check_bill, record_check_result
from payables.application.ingest_bill import IngestBillCommand, ingest_bill
from payables.application.start_bill_check import start_bill_check
from payables.domain.checks.check_bill_command import CheckBill
from payables.domain.checks.check_job import CheckJob
from payables.domain.checks.check_result import CheckResult
from payables.domain.principal import Principal
from payables.domain.role import Role
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
                ExceptionOrmRepository(tenant_id),
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


def exceptions_on(bill_id: UUID) -> list[tuple[str, UUID]]:
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            "SELECT rule, related_bill_id FROM exception WHERE bill_id = %s ORDER BY rule",
            [bill_id],
        )
        return list(cursor.fetchall())
