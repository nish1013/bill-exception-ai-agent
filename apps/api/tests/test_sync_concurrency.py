import pytest

from payables.adapters.orm.proposals import ProposalSyncOrmRepository
from payables.application.sync import finish_apply, receive_sync_callback
from payables.domain.proposals.proposals import ApplyFixProposal
from payables.domain.proposals.sync import CallbackStatus, SyncAnswer, SyncCallback, SyncResult
from tests.concurrency import race
from tests.proposal_data import open_exception
from tests.sync_data import (
    RecordingCallbacks,
    actions_sync,
    apply_now,
    approved_proposal,
    proposal_status,
    stub,
    sync_keys,
)
from tests.tenants import T1

pytestmark = pytest.mark.usefixtures("po_100")


@pytest.fixture
def syncing_p1(committed_db):
    """P1 with two holds, both accepted by the stub, so each waits for its callback."""
    b2, e1 = open_exception("K1")
    b3, e3 = open_exception("K3")
    proposal = approved_proposal([e1, e3], b2, b3)
    apply_now(proposal, stub("callback", RecordingCallbacks()))
    return proposal


def _callback(sync_key):
    def call():
        callback = SyncCallback(sync_key, CallbackStatus.SUCCEEDED)
        return receive_sync_callback(callback, ProposalSyncOrmRepository(T1))

    return call


def _worker_records_synced(proposal, sync_key):
    def call():
        results = [SyncResult(sync_key, SyncAnswer.SYNCED)]
        command = ApplyFixProposal(T1, proposal)
        return finish_apply(command, results, False, ProposalSyncOrmRepository(T1))

    return call


def test_i11_two_callbacks_for_two_actions_of_p1_p1_synced(syncing_p1):
    first, second = sync_keys(syncing_p1)

    result = race(T1, _callback(first), _callback(second))

    assert result.errors == []
    assert [status for _, status, _ in actions_sync(syncing_p1)] == ["synced", "synced"]
    assert proposal_status(syncing_p1) == "synced"


def test_i11_callback_and_worker_answer_for_two_actions_p1_synced(syncing_p1):
    first, second = sync_keys(syncing_p1)

    result = race(T1, _callback(first), _worker_records_synced(syncing_p1, second))

    assert result.errors == []
    assert proposal_status(syncing_p1) == "synced"
