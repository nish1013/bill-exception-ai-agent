from datetime import date

from tests.check_data import add_bill, check, exceptions_on, fail, job_row, start_job
from tests.concurrency import owner_count
from tests.tenants import T2


def test_us6_b2_duplicate_of_b1(committed_db):
    b1 = add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    j1 = start_job([b1, b2])

    check(j1.id, b1)
    check(j1.id, b2)

    assert exceptions_on(b2) == [("duplicate", b1)]
    assert exceptions_on(b1) == []
    assert job_row(j1.id) == ("completed", 0)


def test_us6_b3_possible_duplicate_of_b1(committed_db):
    b1 = add_bill("K1", issue_date=date(2026, 10, 1))
    b3 = add_bill("K3", invoice_number="INV-002", issue_date=date(2026, 10, 5))
    j1 = start_job([b3])

    check(j1.id, b3)

    assert exceptions_on(b3) == [("possible_duplicate", b1)]


def test_us6_recheck_adds_no_second_exception(committed_db):
    b1 = add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    j1 = start_job([b2])
    check(j1.id, b2)

    j2 = start_job([b2])
    check(j2.id, b2)

    assert exceptions_on(b2) == [("duplicate", b1)]


def test_d42_repeat_delivery_changes_nothing(committed_db):
    add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    j1 = start_job([b2])
    check(j1.id, b2)

    check(j1.id, b2)

    assert owner_count("exception") == 1
    assert owner_count("check_job_bill", "job_id = %s AND result = 'ok'", [j1.id]) == 1
    assert job_row(j1.id) == ("completed", 0)


def test_us6_j1_completed_with_one_failed(committed_db):
    b1, b2 = add_bill("K1"), add_bill("K2", invoice_number="INV-002")
    b3 = add_bill("K3", invoice_number="INV-003")
    j1 = start_job([b1, b2, b3])

    fail(j1.id, b3)
    assert job_row(j1.id) == ("running", 1)
    check(j1.id, b1)
    check(j1.id, b2)

    assert job_row(j1.id) == ("completed", 1)


def test_d41_job_failed_when_every_bill_failed(committed_db):
    b1, b2 = add_bill("K1"), add_bill("K2", invoice_number="INV-002")
    j1 = start_job([b1, b2])

    fail(j1.id, b1)
    fail(j1.id, b2)

    assert job_row(j1.id) == ("failed", 2)


def test_us6_t2_bill_never_matches_t1_bill(committed_db):
    add_bill("K1", tenant_id=T2)
    b1 = add_bill("K1")
    j1 = start_job([b1])

    check(j1.id, b1)

    assert exceptions_on(b1) == []
