from datetime import date

import pytest

from payables.domain.supplier_identity import SupplierIdentity
from tests.check_data import (
    add_bill,
    add_po,
    check,
    exception_id,
    exceptions_on,
    fail,
    job_row,
    plant_resolution,
    resolutions_of,
    start_job,
)
from tests.concurrency import owner_count
from tests.tenants import T2

pytestmark = pytest.mark.usefixtures("po_100")


def _checked(bill_id) -> None:
    check(start_job([bill_id]).id, bill_id)


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


def test_us6_b4_amount_differs_from_po_100(committed_db):
    b4 = add_bill("K4", invoice_number="INV-004", amount=125000)

    _checked(b4)

    assert exceptions_on(b4) == [("po_mismatch", None)]


def test_us6_b5_po_999_does_not_exist(committed_db):
    b5 = add_bill("K5", invoice_number="INV-005", po_number="PO-999")

    _checked(b5)

    assert exceptions_on(b5) == [("po_mismatch", None)]


def test_us6_b1_matches_po_100(committed_db):
    b1 = add_bill("K1")

    _checked(b1)

    assert exceptions_on(b1) == []


def test_us6_po_of_other_supplier_is_mismatch(committed_db):
    add_po("PO-200", supplier=SupplierIdentity.parse("Other Co", "GB777"))
    b4 = add_bill("K4", invoice_number="INV-004", po_number="PO-200")

    _checked(b4)

    assert exceptions_on(b4) == [("po_mismatch", None)]


def test_us6_bill_with_no_po_number_no_po_check(committed_db):
    b8 = add_bill("K8", invoice_number="INV-008", po_number=None)

    _checked(b8)

    assert exceptions_on(b8) == []


def test_us6_b6_no_vat_amount(committed_db):
    b6 = add_bill("K6", invoice_number="INV-006", vat_amount=None)

    _checked(b6)

    assert exceptions_on(b6) == [("missing_vat", None)]


def test_us6_zero_vat_is_not_missing(committed_db):
    b6 = add_bill("K6", invoice_number="INV-006", vat_amount=0)

    _checked(b6)

    assert exceptions_on(b6) == []


def test_us6_b7_receipt_no(committed_db):
    b7 = add_bill("K7", invoice_number="INV-007", has_receipt=False)

    _checked(b7)

    assert exceptions_on(b7) == [("missing_receipt", None)]


def test_us6_ignored_e1_stays_ignored(committed_db):
    add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    _checked(b2)
    e1 = exception_id(b2, "duplicate")
    plant_resolution(e1, "ignore", "c1", "Agreed with supplier")

    _checked(b2)

    assert resolutions_of(e1) == [("ignore", "c1", "Agreed with supplier")]
    assert owner_count("exception", "bill_id = %s", [b2]) == 1


def test_us6_e1_resolved_by_system_when_po_added(committed_db):
    b5 = add_bill("K5", invoice_number="INV-005", po_number="PO-999")
    _checked(b5)
    e1 = exception_id(b5, "po_mismatch")
    add_po("PO-999")

    _checked(b5)

    assert resolutions_of(e1) == [("system", "system", None)]


def test_d35_recheck_finds_problem_again_reopens(committed_db):
    add_bill("K1")
    b2 = add_bill("K2", invoice_number="inv 001")
    _checked(b2)
    e1 = exception_id(b2, "duplicate")
    plant_resolution(e1, "system", "system", None)

    _checked(b2)

    assert resolutions_of(e1) == []


def test_d6_system_resolve_is_kept_on_recheck(committed_db):
    b5 = add_bill("K5", invoice_number="INV-005", po_number="PO-999")
    _checked(b5)
    e1 = exception_id(b5, "po_mismatch")
    add_po("PO-999")
    _checked(b5)

    _checked(b5)

    assert resolutions_of(e1) == [("system", "system", None)]
