import pytest
from django.db import IntegrityError, ProgrammingError, connection, connections, transaction

from payables.adapters.orm.tenants import tenant_transaction
from tests.approval_data import drafting_proposal
from tests.check_data import (
    C9,
    add_bill,
    check,
    exception_id,
    plant_resolution,
    resolutions_of,
    start_job,
)
from tests.tenants import T1, T2

pytestmark = pytest.mark.usefixtures("po_100")

T2_RESOLUTION = """
INSERT INTO resolution (exception_id, tenant_id, kind, actor, reason, created_at)
VALUES (%s, %s, 'ignore', 'c1', 'reason', now())
"""


def _e2(tenant_id=T1):
    bill = add_bill("K7", tenant_id, invoice_number="INV-007", has_receipt=False)
    check(start_job([bill], tenant_id).id, bill, tenant_id)
    return exception_id(bill, "missing_receipt")


def _app_sql(sql: str, params: list) -> int:
    with tenant_transaction(T1), connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.rowcount


@pytest.mark.parametrize(
    ("kind", "actor", "reason"),
    [
        ("ignore", "c1", None),
        ("ignore", "c1", ""),
        ("ignore", "c1", "  "),
        ("ignore", "system", "Agreed with supplier"),
        ("ignore", "", "Agreed with supplier"),
        ("system", "system", "Agreed with supplier"),
        ("system", "c1", None),
        ("proposal", "a1", None),
        ("approve", "a1", "reason"),
    ],
)
def test_i8_resolution_refuses_kind_without_its_fields(committed_db, kind, actor, reason):
    e2 = _e2()

    with pytest.raises(IntegrityError, match="resolution_kind_fields"):
        with transaction.atomic(using="owner"):
            plant_resolution(e2, kind, actor, reason)


@pytest.mark.parametrize(
    "fields", [("ignore", "c1", "Agreed with supplier"), ("system", "system", None)]
)
def test_i8_resolution_accepts_kind_with_its_fields(committed_db, fields):
    e2 = _e2()

    plant_resolution(e2, *fields)

    assert resolutions_of(e2) == [fields]


def test_i1_resolution_of_t2_exception_refused(committed_db):
    e9 = _e2(T2)

    with pytest.raises(IntegrityError, match="resolution_tenant_exception_id_fkey"):
        with transaction.atomic(using="owner"), connections["owner"].cursor() as cursor:
            cursor.execute(T2_RESOLUTION, [e9, T1])


def test_d35_app_role_cannot_update_resolution(committed_db):
    e2 = _e2()
    plant_resolution(e2, "ignore", "c1", "Agreed with supplier")

    with pytest.raises(ProgrammingError, match="permission denied"):
        _app_sql("UPDATE resolution SET reason = 'changed' WHERE exception_id = %s", [e2])


def test_d29_app_role_cannot_delete_ignore(committed_db):
    e2 = _e2()
    plant_resolution(e2, "ignore", "c1", "Agreed with supplier")

    assert _app_sql("DELETE FROM resolution WHERE exception_id = %s", [e2]) == 0
    assert resolutions_of(e2) == [("ignore", "c1", "Agreed with supplier")]


def test_d35_app_role_deletes_system_resolve(committed_db):
    e2 = _e2()
    plant_resolution(e2, "system", "system", None)

    assert _app_sql("DELETE FROM resolution WHERE exception_id = %s", [e2]) == 1


PROPOSAL_RESOLUTION = """
INSERT INTO resolution (exception_id, tenant_id, kind, actor, reason, proposal_id, created_at)
SELECT id, tenant_id, %s, %s, %s, %s, now() FROM exception WHERE id = %s
"""


def _plant_with_proposal(exception, kind, actor, reason, proposal) -> None:
    with transaction.atomic(using="owner"), connections["owner"].cursor() as cursor:
        cursor.execute(PROPOSAL_RESOLUTION, [kind, actor, reason, proposal, exception])


@pytest.mark.parametrize(
    ("kind", "actor", "reason"),
    [
        ("proposal", "system", None),
        ("proposal", " ", None),
        ("proposal", "a1", "Agreed with supplier"),
        ("ignore", "c1", "Agreed with supplier"),
        ("system", "system", None),
    ],
)
def test_i8_proposal_resolution_needs_approver_and_proposal_only(committed_db, kind, actor, reason):
    e2 = _e2()
    p1 = drafting_proposal([e2])

    with pytest.raises(IntegrityError, match="resolution_kind_fields"):
        _plant_with_proposal(e2, kind, actor, reason, p1)


def test_i8_proposal_resolution_with_approver_and_proposal_accepted(committed_db):
    e2 = _e2()
    p1 = drafting_proposal([e2])

    _plant_with_proposal(e2, "proposal", "a1", None, p1)

    assert resolutions_of(e2) == [("proposal", "a1", None)]


def test_i1_resolution_refers_to_proposal_of_same_tenant(committed_db):
    e2 = _e2()
    e9 = _e2(T2)
    p9 = drafting_proposal([e9], requested_by=C9)

    with pytest.raises(IntegrityError, match="resolution_tenant_proposal_id_fkey"):
        _plant_with_proposal(e2, "proposal", "a1", None, p9)
