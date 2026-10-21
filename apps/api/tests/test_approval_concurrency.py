import pytest
from django.db import IntegrityError, connection

from payables.adapters.orm.exceptions import ExceptionOrmRepository, ResolutionOrmRepository
from payables.adapters.orm.tenants import tenant_transaction
from payables.application.exceptions import ignore_exception
from payables.domain.errors import ConflictError, ResolutionExistsError, StaleProposalError
from tests.approval_data import (
    A1,
    A2,
    apply_messages,
    approve,
    drafting_proposal,
    now,
    pending_proposal,
    proposal_resolutions,
    proposal_state,
    reject,
)
from tests.check_data import (
    C1,
    add_bill,
    add_po,
    check,
    check_in_transaction,
    exception_id,
    start_job,
)
from tests.concurrency import race
from tests.proposal_data import open_exception
from tests.tenants import T1

pytestmark = pytest.mark.usefixtures("po_100")


def _ignore(exception):
    def call() -> None:
        ignore_exception(
            C1, exception, "Paid by card", ExceptionOrmRepository(T1), ResolutionOrmRepository(T1)
        )

    return call


def _open_po_mismatch():
    b5 = add_bill("K5", invoice_number="INV-005", po_number="PO-999")
    check(start_job([b5]).id, b5)
    return b5, exception_id(b5, "po_mismatch")


def test_i7_approve_p1_and_p2_on_e1_one_wins_other_stale(committed_db):
    b2, e1 = open_exception("K1")
    p1 = pending_proposal([e1], b2)
    p2 = pending_proposal([e1], b2)

    result = race(T1, approve(A1, p1), approve(A2, p2))

    assert result.errors == []
    assert type(result.second) is StaleProposalError
    assert (proposal_state(p1)[0], proposal_state(p2)[0]) == ("approved", "stale")
    assert proposal_resolutions(e1) == [("proposal", "a1", p1)]
    assert (apply_messages(p1), apply_messages(p2)) == (1, 0)


def test_i7_approve_p1_then_ignore_e1_409(committed_db):
    b2, e1 = open_exception("K1")
    p1 = pending_proposal([e1], b2)

    result = race(T1, approve(A1, p1), _ignore(e1))

    assert [type(error) for error in result.errors] == [ResolutionExistsError]
    assert proposal_state(p1)[0] == "approved"
    assert proposal_resolutions(e1) == [("proposal", "a1", p1)]


def test_i7_ignore_e1_then_approve_p1_stale(committed_db):
    b2, e1 = open_exception("K1")
    p1 = pending_proposal([e1], b2)

    result = race(T1, _ignore(e1), approve(A1, p1))

    assert type(result.second) is StaleProposalError
    assert proposal_state(p1)[0] == "stale"
    assert [row[:2] for row in proposal_resolutions(e1)] == [("ignore", "c1")]
    assert apply_messages(p1) == 0


def test_i7_approve_p1_then_recheck_e1_stays_pending_sync(committed_db):
    b5, e1 = _open_po_mismatch()
    p1 = pending_proposal([e1], b5)
    add_po("PO-999")
    recheck = check_in_transaction(start_job([b5]).id, b5)

    result = race(T1, approve(A1, p1), recheck)

    assert result.errors == []
    assert proposal_resolutions(e1) == [("proposal", "a1", p1)]


def test_i7_recheck_resolves_e1_then_approve_p1_stale(committed_db):
    b5, e1 = _open_po_mismatch()
    p1 = pending_proposal([e1], b5)
    add_po("PO-999")
    recheck = check_in_transaction(start_job([b5]).id, b5)

    result = race(T1, recheck, approve(A1, p1))

    assert type(result.second) is StaleProposalError
    assert proposal_state(p1)[0] == "stale"
    assert [row[:2] for row in proposal_resolutions(e1)] == [("system", "system")]


def test_i9_a1_and_a2_approve_p1_one_wins_one_apply_job(committed_db):
    b2, e1 = open_exception("K1")
    p1 = pending_proposal([e1], b2)

    result = race(T1, approve(A1, p1), approve(A2, p1))

    assert [type(error) for error in result.errors] == [ConflictError]
    assert proposal_state(p1) == ("approved", "a1", None)
    assert apply_messages(p1) == 1


def test_i9_reject_and_approve_p1_reject_wins(committed_db):
    b2, e1 = open_exception("K1")
    p1 = pending_proposal([e1], b2)

    result = race(T1, reject(A1, p1, "Wrong supplier"), approve(A2, p1))

    assert [type(error) for error in result.errors] == [ConflictError]
    assert proposal_state(p1) == ("rejected", None, "Wrong supplier")
    assert proposal_resolutions(e1) == []
    assert apply_messages(p1) == 0


def test_i9_drafting_p1_approve_409_no_resolution(committed_db):
    _, e1 = open_exception("K1")
    p1 = drafting_proposal([e1])

    with pytest.raises(ConflictError):
        now(approve(A1, p1))

    assert proposal_state(p1) == ("drafting", None, None)
    assert proposal_resolutions(e1) == []
    assert apply_messages(p1) == 0


def test_i9_database_refuses_approver_who_is_requester(committed_db):
    b2, e1 = open_exception("K1")
    p1 = pending_proposal([e1], b2)

    with pytest.raises(IntegrityError, match="proposal_four_eyes"):
        with tenant_transaction(T1), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE proposal SET status = 'approved', approved_by = requested_by, "
                "approved_at = now() WHERE id = %s",
                [p1],
            )

    assert proposal_state(p1) == ("pending", None, None)


def test_i9_database_refuses_approved_status_with_no_approver(committed_db):
    b2, e1 = open_exception("K1")
    p1 = pending_proposal([e1], b2)

    with pytest.raises(IntegrityError, match="proposal_approval_fields"):
        with tenant_transaction(T1), connection.cursor() as cursor:
            cursor.execute("UPDATE proposal SET status = 'approved' WHERE id = %s", [p1])


def test_i7_app_role_cannot_delete_a_proposal_resolution(committed_db):
    b2, e1 = open_exception("K1")
    p1 = pending_proposal([e1], b2)
    now(approve(A1, p1))

    with tenant_transaction(T1), connection.cursor() as cursor:
        cursor.execute("DELETE FROM resolution WHERE exception_id = %s", [e1])
        assert cursor.rowcount == 0

    assert proposal_resolutions(e1) == [("proposal", "a1", p1)]
