import pytest

from config.celery import app
from payables.adapters.broker import PROPOSE_AI, CeleryPublisher
from payables.adapters.outbox import OutboxRelay
from tests.broker import process_env, running, wait_until, worker_command
from tests.proposal_data import actions_of, open_exception, proposal_row, request_now

pytestmark = pytest.mark.usefixtures("po_100")


def test_us11_worker_drafts_p1_from_the_propose_ai_queue(committed_db, queues):
    b2, e1 = open_exception("K2")
    p1 = request_now([e1])

    assert OutboxRelay(CeleryPublisher(app)).publish_pending() == 2
    with running(worker_command(PROPOSE_AI), process_env(queues, LLM_PROVIDER="stub")):
        wait_until(lambda: proposal_row(p1)[0] != "drafting", "P1 is drafted")

    assert proposal_row(p1) == ("pending", None)
    assert actions_of(p1) == [("hold", b2, None)]
