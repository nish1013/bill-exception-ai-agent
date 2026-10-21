import json
from uuid import UUID, uuid4

import pytest
from django.db import connections

from payables.adapters.orm.checks import CheckJobOrmRepository
from payables.adapters.orm.exceptions import ExceptionOrmRepository
from payables.adapters.orm.outbox import OutboxOrmRepository
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.checks import recheck_po_mismatches
from payables.domain.checks.jobs import recheck_jobs
from payables.domain.errors import ConflictError
from payables.domain.purchase_orders import PurchaseOrderAdded
from tests.check_data import (
    add_bill,
    add_po,
    check,
    exception_id,
    plant_resolution,
    resolutions_of,
    start_job,
)
from tests.concurrency import owner_count
from tests.tenants import T1, T2

pytestmark = pytest.mark.usefixtures("po_100")


def _events() -> list[dict]:
    with connections["owner"].cursor() as cursor:
        cursor.execute("SELECT payload FROM outbox WHERE command = 'PurchaseOrderAdded'")
        return [json.loads(row[0]) for row in cursor.fetchall()]


def _system_jobs() -> list[tuple[UUID, list[UUID]]]:
    with connections["owner"].cursor() as cursor:
        cursor.execute(
            "SELECT j.id, array_agg(b.bill_id ORDER BY b.bill_id) FROM check_job j "
            "JOIN check_job_bill b ON b.job_id = j.id WHERE j.requested_by = 'system' "
            "GROUP BY j.id"
        )
        return list(cursor.fetchall())


def _deliver(payload: dict) -> int:
    event = PurchaseOrderAdded(
        UUID(payload["event_id"]), UUID(payload["tenant_id"]), payload["po_number"]
    )
    with tenant_transaction(event.tenant_id):
        return recheck_po_mismatches(
            event,
            ExceptionOrmRepository(event.tenant_id),
            CheckJobOrmRepository(event.tenant_id),
            OutboxOrmRepository(event.tenant_id),
        )


def _open_mismatch(key: str, po_number: str = "PO-999", tenant_id=T1, **changes):
    bill = add_bill(key, tenant_id, invoice_number=f"INV-{key}", po_number=po_number, **changes)
    check(start_job([bill], tenant_id).id, bill, tenant_id)
    return bill, exception_id(bill, "po_mismatch")


def test_i16_po_999_added_writes_event(committed_db):
    add_po("PO-999")

    assert [(event["tenant_id"], event["po_number"]) for event in _events()] == [(str(T1), "PO999")]


def test_i16_po_999_resolves_b5_by_system(committed_db):
    b5, e1 = _open_mismatch("K5")
    add_po("po 999")

    assert _deliver(_events()[0]) == 1
    [(job_id, bill_ids)] = _system_jobs()
    assert bill_ids == [b5]
    check(job_id, b5)

    assert resolutions_of(e1) == [("system", "system", None)]
    assert (
        owner_count("outbox", "command = 'CheckBill' AND payload->>'job_id' = %s", [str(job_id)])
        == 1
    )


def test_i16_repeat_event_starts_no_second_job(committed_db):
    _open_mismatch("K5")
    add_po("PO-999")
    event = _events()[0]
    _deliver(event)

    assert _deliver(event) == 0
    assert len(_system_jobs()) == 1


def test_i16_ignored_mismatch_not_checked(committed_db):
    _, e1 = _open_mismatch("K5")
    plant_resolution(e1, "ignore", "c1", "Agreed with supplier")
    add_po("PO-999")

    assert _deliver(_events()[0]) == 0
    assert _system_jobs() == []


def test_i16_only_bills_on_the_new_po_number(committed_db):
    _open_mismatch("K4", po_number="PO-100", amount=125000)
    b5, _ = _open_mismatch("K5")
    add_po("PO-999")

    _deliver(_events()[0])

    assert [bills for _, bills in _system_jobs()] == [[b5]]


def test_i16_t2_bill_not_checked_for_t1_po(committed_db):
    _open_mismatch("K95", tenant_id=T2)
    add_po("PO-999")

    assert _deliver(_events()[0]) == 0


def test_i16_po_conflict_writes_no_event(committed_db):
    _open_mismatch("K5")
    add_po("PO-999")

    with pytest.raises(ConflictError):
        add_po("po 999")

    assert len(_events()) == 1


def test_i16_recheck_of_1001_bills_in_three_jobs():
    event_id = uuid4()
    bill_ids = [UUID(int=n) for n in range(1001)]

    jobs = recheck_jobs(event_id, bill_ids)

    assert [len(job.bill_ids) for job in jobs] == [500, 500, 1]
    assert [bill for job in jobs for bill in job.bill_ids] == bill_ids
    assert len({job.id for job in jobs}) == 3
    assert [job.id for job in recheck_jobs(event_id, bill_ids)] == [job.id for job in jobs]
