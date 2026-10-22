from uuid import UUID

import pytest

from tests.approval_data import pending_proposal
from tests.check_data import C9
from tests.proposal_data import open_exception
from tests.sync_data import (
    CALLBACK_PATH,
    CALLBACK_SECRET,
    RecordingCallbacks,
    actions_sync,
    apply_now,
    approved_proposal,
    callback_body,
    force_status,
    post_callback,
    proposal_status,
    signed,
    stub,
    sync_keys,
)
from tests.tenants import T2

pytestmark = pytest.mark.usefixtures("po_100")


@pytest.fixture(autouse=True)
def callback_secret(settings) -> None:
    settings.ACCOUNTING_CALLBACK_SECRET = CALLBACK_SECRET


@pytest.fixture
def syncing_p1(committed_db):
    """P1 with one hold, which the stub accepted in callback mode."""
    b2, e1 = open_exception("K1")
    proposal = approved_proposal([e1], b2)
    apply_now(proposal, stub("callback", RecordingCallbacks()))
    assert proposal_status(proposal) == "syncing"
    return proposal


@pytest.fixture
def syncing_p1_two_actions(committed_db):
    b2, e1 = open_exception("K1")
    b3, e3 = open_exception("K3")
    proposal = approved_proposal([e1, e3], b2, b3)
    apply_now(proposal, stub("callback", RecordingCallbacks()))
    return proposal


def _callback(client, sync_key: UUID, **changes):
    body = callback_body(sync_key, **changes)
    return post_callback(client, body, signed(body))


def test_us16_valid_succeeded_callback_action_synced_p1_synced(syncing_p1, client):
    response = _callback(client, sync_keys(syncing_p1)[0])

    assert response.status_code == 200
    assert [status for _, status, _ in actions_sync(syncing_p1)] == ["synced"]
    assert proposal_status(syncing_p1) == "synced"


def test_us16_first_of_two_callbacks_p1_stays_syncing(syncing_p1_two_actions, client):
    first, second = sync_keys(syncing_p1_two_actions)

    _callback(client, first)

    assert [status for _, status, _ in actions_sync(syncing_p1_two_actions)] == [
        "synced",
        "accepted",
    ]
    assert proposal_status(syncing_p1_two_actions) == "syncing"
    _callback(client, second)
    assert proposal_status(syncing_p1_two_actions) == "synced"


@pytest.mark.parametrize(
    "signature",
    [None, "", "sha256=00", "garbage", signed(b"another body")],
    ids=["missing", "empty", "short", "no-prefix", "other-body"],
)
def test_us16_bad_signature_401_nothing_written(syncing_p1, client, signature):
    before = actions_sync(syncing_p1)

    response = post_callback(client, callback_body(sync_keys(syncing_p1)[0]), signature)

    assert response.status_code == 401
    assert actions_sync(syncing_p1) == before
    assert proposal_status(syncing_p1) == "syncing"


def test_us16_signature_with_another_secret_401(syncing_p1, client):
    body = callback_body(sync_keys(syncing_p1)[0])

    response = post_callback(client, body, signed(body, secret="not-the-secret"))

    assert response.status_code == 401
    assert proposal_status(syncing_p1) == "syncing"


def test_us16_same_callback_again_200_nothing_changes(syncing_p1, client):
    key = sync_keys(syncing_p1)[0]
    _callback(client, key)
    before = actions_sync(syncing_p1)

    response = _callback(client, key)

    assert response.status_code == 200
    assert actions_sync(syncing_p1) == before
    assert proposal_status(syncing_p1) == "synced"


def test_us16_unknown_provider_404(syncing_p1, client):
    body = callback_body(sync_keys(syncing_p1)[0])

    response = post_callback(client, body, signed(body), path="/callbacks/accounting/xero")

    assert response.status_code == 404
    assert proposal_status(syncing_p1) == "syncing"


def test_us16_unknown_sync_key_404(syncing_p1, client):
    response = _callback(client, UUID(int=99))

    assert response.status_code == 404


def test_us16_callback_for_a_t2_key_changes_only_the_t2_action(syncing_p1, client):
    b9, e9 = open_exception("K9", tenant_id=T2)
    t2_proposal = pending_proposal([e9], b9, requested_by=C9)
    force_status(t2_proposal, "syncing")

    response = _callback(client, sync_keys(t2_proposal)[0])

    assert response.status_code == 200
    assert proposal_status(t2_proposal) == "synced"
    assert proposal_status(syncing_p1) == "syncing"
    assert [status for _, status, _ in actions_sync(syncing_p1)] == ["accepted"]


@pytest.mark.parametrize(
    "body",
    [b"not json", b"[]", b'{"status": "succeeded"}', b'{"sync_key": "2", "status": "succeeded"}'],
    ids=["text", "list", "key-missing", "bad-key"],
)
def test_us16_signed_body_that_is_not_a_callback_400(syncing_p1, client, body):
    response = post_callback(client, body, signed(body))

    assert response.status_code == 400


def test_us16_status_other_than_succeeded_400(syncing_p1, client):
    response = _callback(client, sync_keys(syncing_p1)[0], status="failed")

    assert response.status_code == 400
    assert proposal_status(syncing_p1) == "syncing"


def test_us16_get_is_not_allowed(client):
    assert client.get(CALLBACK_PATH).status_code == 405
