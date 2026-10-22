from uuid import UUID

import pytest

from config.celery import app
from payables.adapters.broker import APPLY, CeleryPublisher
from payables.adapters.channels import console_event_message
from payables.adapters.outbox import OutboxRelay
from payables.domain.proposals.proposals import ActionKind, DraftAction, ProposalStatus
from payables.domain.proposals.sync import ProposalSyncChanged
from tests.approval_data import apply_messages
from tests.broker import process_env, queue_stats, running, wait_until, worker_command
from tests.proposal_data import audit_of, open_exception
from tests.sync_data import (
    CountingAccounting,
    FailingAccounting,
    RecordingCallbacks,
    actions_sync,
    apply_now,
    apply_until_done,
    approved_proposal,
    drafted_proposal,
    force_status,
    ledger_count,
    ledger_keys,
    proposal_status,
    stub,
    sync_keys,
)
from tests.tenants import T1

pytestmark = pytest.mark.usefixtures("po_100")

EXCEPTIONS = "query { exceptions { items { id status } } }"


@pytest.fixture
def p1(committed_db):
    b2, e1 = open_exception("K1")
    _, e4 = open_exception("K4")
    return approved_proposal([e1, e4], b2), e1, e4


def _statuses(graphql, token_for) -> dict[str, str]:
    response = graphql(EXCEPTIONS, token_for("c1"))
    return {item["id"]: item["status"] for item in response.json()["data"]["exceptions"]["items"]}


def test_us14_worker_runs_p1_synced_stub_holds_key_exceptions_resolved(p1, graphql, token_for):
    proposal, e1, e4 = p1

    outcome = apply_now(proposal, stub("ok"))

    assert outcome is not None
    assert outcome.changed == ProposalSyncChanged(proposal, ProposalStatus.SYNCED)
    assert proposal_status(proposal) == "synced"
    assert ledger_keys() == sync_keys(proposal)
    assert [(status, attempts) for _, status, attempts in actions_sync(proposal)] == [("synced", 0)]
    statuses = _statuses(graphql, token_for)
    assert (statuses[str(e1)], statuses[str(e4)]) == ("resolved", "resolved")


def test_us14_syncing_p1_key_known_second_delivery_posts_nothing_new(p1):
    proposal, _, _ = p1
    accounting = CountingAccounting(stub("ok"))
    apply_now(proposal, accounting)

    assert apply_now(proposal, accounting) is None

    assert accounting.calls == 1
    assert ledger_count(sync_keys(proposal)[0]) == 1
    assert proposal_status(proposal) == "synced"


def test_us14_stub_answers_a_known_key_with_no_new_post(p1):
    proposal, _, _ = p1
    callbacks = RecordingCallbacks()
    accounting = stub("callback", callbacks)
    apply_now(proposal, accounting)
    with pytest.MonkeyPatch.context() as patch:
        # The worker sent the action, then died before it stored the answer.
        patch.setattr(
            "payables.adapters.orm.proposals.ProposalSyncOrmRepository.record_results",
            lambda *args: None,
        )
        apply_now(proposal, accounting)

    assert ledger_count(sync_keys(proposal)[0]) == 1
    assert callbacks.scheduled == sync_keys(proposal)


def test_us14_adapter_fails_each_call_5_attempts_sync_failed(p1, graphql, token_for):
    proposal, e1, e4 = p1
    accounting = FailingAccounting()

    deliveries = apply_until_done(proposal, accounting)

    assert (deliveries, accounting.calls) == (5, 5)
    assert proposal_status(proposal) == "sync_failed"
    assert [(status, attempts) for _, status, attempts in actions_sync(proposal)] == [
        ("pending", 5)
    ]
    assert [kind for kind, _, _ in audit_of(proposal)] == ["proposal_approved"]
    statuses = _statuses(graphql, token_for)
    assert (statuses[str(e1)], statuses[str(e4)]) == ("pending_sync", "pending_sync")


def test_us14_fourth_failure_asks_for_a_retry_fifth_does_not(p1):
    proposal, _, _ = p1

    fourth = apply_now(proposal, FailingAccounting(), retries=3)
    fifth = apply_now(proposal, FailingAccounting(), retries=4)

    assert fourth is not None and (fourth.retry, fourth.changed) == (True, None)
    assert fifth is not None and fifth.retry is False
    assert fifth.changed == ProposalSyncChanged(proposal, ProposalStatus.SYNC_FAILED)


def test_us14_one_action_fails_the_synced_one_is_not_sent_again(committed_db):
    b2, e1 = open_exception("K1")
    b3, e3 = open_exception("K3")
    proposal = approved_proposal([e1, e3], b2, b3)
    first, second = sync_keys(proposal)

    class SecondFails:
        def send(self, action):
            if action.sync_key == second:
                return FailingAccounting().send(action)
            return stub("ok").send(action)

    outcome = apply_now(proposal, SecondFails())
    accounting = CountingAccounting(stub("ok"))
    apply_now(proposal, accounting, retries=1)

    assert outcome is not None and outcome.retry is True
    assert accounting.calls == 1
    assert actions_sync(proposal) == [(first, "synced", 0), (second, "synced", 1)]
    assert proposal_status(proposal) == "synced"


def test_us14_callback_mode_p1_stays_syncing_with_the_action_accepted(p1):
    proposal, _, _ = p1
    callbacks = RecordingCallbacks()

    outcome = apply_now(proposal, stub("callback", callbacks))

    assert outcome is not None and (outcome.changed, outcome.retry) == (None, False)
    assert proposal_status(proposal) == "syncing"
    assert [status for _, status, _ in actions_sync(proposal)] == ["accepted"]
    assert callbacks.scheduled == sync_keys(proposal)


def test_us14_accepted_action_is_not_sent_again_on_a_second_delivery(p1):
    proposal, _, _ = p1
    callbacks = RecordingCallbacks()
    apply_now(proposal, stub("callback", callbacks))
    accounting = CountingAccounting(stub("callback", callbacks))

    apply_now(proposal, accounting)

    assert accounting.calls == 0
    assert len(callbacks.scheduled) == 1
    assert proposal_status(proposal) == "syncing"


@pytest.mark.parametrize("status", ["pending", "rejected", "sync_failed", "synced"])
def test_us14_proposal_not_approved_or_syncing_is_not_applied(committed_db, status):
    b2, e1 = open_exception("K1")
    proposal = drafted_proposal([e1], [DraftAction(ActionKind.HOLD, b2)])
    force_status(proposal, status)
    accounting = CountingAccounting(stub("ok"))

    assert apply_now(proposal, accounting) is None

    assert accounting.calls == 0
    assert proposal_status(proposal) == status


def test_us14_proposal_sync_changed_console_message():
    changed = ProposalSyncChanged(UUID(int=1), ProposalStatus.SYNCED)

    assert console_event_message(changed) == {
        "type": "ProposalSyncChanged",
        "proposalId": str(UUID(int=1)),
        "status": "synced",
    }


def test_us14_worker_applies_p1_from_the_apply_queue(p1, queues):
    proposal, _, _ = p1
    assert apply_messages(proposal) == 1

    OutboxRelay(CeleryPublisher(app)).publish_pending()
    with running(worker_command(APPLY), process_env(queues, ACCOUNTING_STUB_MODE="ok")):
        wait_until(lambda: proposal_status(proposal) == "synced", "P1 is synced")

    assert ledger_keys() == sync_keys(proposal)


def test_us14_same_apply_message_twice_one_post_at_the_stub(p1, queues):
    proposal, _, _ = p1
    publisher = CeleryPublisher(app)
    OutboxRelay(publisher).publish_pending()
    payload = {"tenant_id": str(T1), "proposal_id": str(proposal)}
    publisher.publish(UUID(int=7), "ApplyFixProposal", payload)

    with running(worker_command(APPLY), process_env(queues, ACCOUNTING_STUB_MODE="ok")):
        wait_until(lambda: _apply_queue_empty(queues), "both apply messages are handled")
        wait_until(lambda: proposal_status(proposal) == "synced", "P1 is synced")

    assert ledger_count(sync_keys(proposal)[0]) == 1


def test_us14_worker_in_fail_mode_reaches_sync_failed_after_5_attempts(p1, queues):
    proposal, _, _ = p1
    OutboxRelay(CeleryPublisher(app)).publish_pending()
    env = process_env(queues, ACCOUNTING_STUB_MODE="fail", APPLY_FIRST_RETRY_SECONDS="0")

    with running(worker_command(APPLY), env):
        wait_until(lambda: proposal_status(proposal) == "sync_failed", "P1 is sync_failed")

    assert [attempts for _, _, attempts in actions_sync(proposal)] == [5]
    assert ledger_keys() == []


def _apply_queue_empty(broker_url: str) -> bool:
    return queue_stats(broker_url, APPLY).ready == 0
