import uuid

import pytest

from tests.check_data import (
    add_bill,
    check,
    exception_id,
    plant_resolution,
    resolutions_of,
    start_job,
)
from tests.ingest_data import error_of
from tests.tenants import T2

pytestmark = pytest.mark.usefixtures("po_100")

IGNORE = """
mutation($id: UUID!, $reason: String!) {
  ignoreException(exceptionId: $id, reason: $reason) { id status resolvedBy reason }
}
"""
INBOX = """
query($status: String) { exceptions(status: $status) { totalCount items { id reason } } }
"""


@pytest.fixture
def ignore(graphql, token_for):
    def call(exception, reason: str = "Agreed with supplier", user: str = "c1"):
        return graphql(IGNORE, token_for(user), {"id": str(exception), "reason": reason})

    return call


def _open_exception(key: str = "K7", tenant_id=None) -> uuid.UUID:
    extra = {} if tenant_id is None else {"tenant_id": tenant_id}
    bill = add_bill(key, invoice_number=f"INV-{key}", has_receipt=False, **extra)
    job = start_job([bill], **extra)
    check(job.id, bill, **extra)
    return exception_id(bill, "missing_receipt")


def _ids(graphql, token: str, status: str) -> list[str]:
    response = graphql(INBOX, token, {"status": status})
    return [item["id"] for item in response.json()["data"]["exceptions"]["items"]]


def test_us9_e2_ignored_with_c1_and_reason(committed_db, ignore):
    e2 = _open_exception()

    response = ignore(e2, "  Agreed with supplier ")

    assert response.json()["data"]["ignoreException"] == {
        "id": str(e2),
        "status": "ignored",
        "resolvedBy": "c1",
        "reason": "Agreed with supplier",
    }
    assert resolutions_of(e2) == [("ignore", "c1", "Agreed with supplier")]


def test_us9_ignored_e2_leaves_open_filter(committed_db, ignore, graphql, token_for):
    e2 = _open_exception()
    ignore(e2)

    assert _ids(graphql, token_for("c1"), "open") == []
    assert _ids(graphql, token_for("c1"), "ignored") == [str(e2)]


@pytest.mark.parametrize("reason", ["", "   ", "\n\t", "x" * 1001])
def test_us9_bad_reason_400_e2_stays_open(committed_db, ignore, reason):
    e2 = _open_exception()

    response = ignore(e2, reason)

    assert error_of(response) == {"code": "VALIDATION", "status": 400}
    assert resolutions_of(e2) == []


def test_us9_reason_of_1000_characters_accepted(committed_db, ignore):
    e2 = _open_exception()

    response = ignore(e2, "x" * 1000)

    assert response.json()["data"]["ignoreException"]["status"] == "ignored"


def test_us9_ignore_of_ignored_409_first_kept(committed_db, ignore):
    e2 = _open_exception()
    ignore(e2, "First reason")

    response = ignore(e2, "Second reason")

    assert error_of(response) == {"code": "CONFLICT", "status": 409}
    assert resolutions_of(e2) == [("ignore", "c1", "First reason")]


def test_us9_ignore_of_resolved_409(committed_db, ignore):
    e3 = _open_exception()
    plant_resolution(e3, "system", "system", None)

    response = ignore(e3)

    assert error_of(response) == {"code": "CONFLICT", "status": 409}
    assert resolutions_of(e3) == [("system", "system", None)]


def test_us9_approver_403(committed_db, ignore):
    e2 = _open_exception()

    response = ignore(e2, user="a1")

    assert error_of(response) == {"code": "FORBIDDEN", "status": 403}
    assert resolutions_of(e2) == []


def test_us9_t2_exception_404(committed_db, ignore):
    e9 = _open_exception("K9", tenant_id=T2)

    response = ignore(e9)

    assert error_of(response) == {"code": "NOT_FOUND", "status": 404}
    assert resolutions_of(e9) == []


def test_us9_unknown_exception_404(committed_db, ignore):
    assert error_of(ignore(uuid.uuid4())) == {"code": "NOT_FOUND", "status": 404}
