import pytest

from payables.adapters.orm.exception_repository import ExceptionOrmRepository
from payables.adapters.orm.resolution_repository import ResolutionOrmRepository
from payables.application.exceptions import ignore_exception
from payables.domain.errors import ConflictError
from tests.check_data import (
    C1,
    add_bill,
    add_po,
    check,
    check_in_transaction,
    exception_id,
    resolutions_of,
    start_job,
)
from tests.concurrency import race
from tests.tenants import T1

pytestmark = pytest.mark.usefixtures("po_100")


def _ignore(exception, reason: str):
    def call() -> None:
        ignore_exception(
            C1, exception, reason, ExceptionOrmRepository(T1), ResolutionOrmRepository(T1)
        )

    return call


def _open_po_mismatch():
    b5 = add_bill("K5", invoice_number="INV-005", po_number="PO-999")
    check(start_job([b5]).id, b5)
    return b5, exception_id(b5, "po_mismatch")


def test_i7_two_ignores_of_e1_one_resolution(committed_db):
    _, e1 = _open_po_mismatch()

    result = race(T1, _ignore(e1, "First"), _ignore(e1, "Second"))

    assert [type(error) for error in result.errors] == [ConflictError]
    assert resolutions_of(e1) == [("ignore", "c1", "First")]


def test_i7_ignore_then_recheck_e1_stays_ignored(committed_db):
    b5, e1 = _open_po_mismatch()
    add_po("PO-999")
    recheck = check_in_transaction(start_job([b5]).id, b5)

    result = race(T1, _ignore(e1, "Agreed with supplier"), recheck)

    assert result.errors == []
    assert resolutions_of(e1) == [("ignore", "c1", "Agreed with supplier")]


def test_i7_recheck_then_ignore_e1_409(committed_db):
    b5, e1 = _open_po_mismatch()
    add_po("PO-999")
    recheck = check_in_transaction(start_job([b5]).id, b5)

    result = race(T1, recheck, _ignore(e1, "Agreed with supplier"))

    assert [type(error) for error in result.errors] == [ConflictError]
    assert resolutions_of(e1) == [("system", "system", None)]
