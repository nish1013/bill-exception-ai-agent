from tests.check_data import (
    add_bill,
    check,
    check_in_transaction,
    exceptions_on,
    job_row,
    start_job,
)
from tests.concurrency import race
from tests.tenants import T1


def test_i6_two_checks_of_b2_one_exception(committed_db):
    b1 = add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    j1, j2 = start_job([b2]), start_job([b2])

    result = race(T1, check_in_transaction(j1.id, b2), check_in_transaction(j2.id, b2))

    assert result.errors == []
    assert exceptions_on(b2) == [("duplicate", b1)]
    assert job_row(j1.id) == job_row(j2.id) == ("completed", 0)


def test_i13_last_two_bills_finish_together(committed_db):
    b1, b2 = add_bill("K1"), add_bill("K2", invoice_number="INV-002")
    b3 = add_bill("K3", invoice_number="INV-003")
    j1 = start_job([b1, b2, b3])
    check(j1.id, b3)

    result = race(T1, check_in_transaction(j1.id, b1), check_in_transaction(j1.id, b2))

    assert result.errors == []
    assert job_row(j1.id) == ("completed", 0)
