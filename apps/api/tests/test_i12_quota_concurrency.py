import pytest
from django.db import IntegrityError, connections

from payables.domain.errors import RateLimitedError
from tests.concurrency import race
from tests.proposal_data import TODAY, open_exception, request, seed_slots, slots_today
from tests.tenants import T1

pytestmark = pytest.mark.usefixtures("po_100")


def test_i12_two_requests_for_slot_50_one_429(committed_db):
    _, e1 = open_exception("K1")
    seed_slots(49)

    result = race(T1, request([e1]), request([e1]))

    assert [type(error) for error in result.errors] == [RateLimitedError]
    assert slots_today() == list(range(1, 51))


def test_i12_two_requests_for_slot_4_loser_takes_5(committed_db):
    _, e1 = open_exception("K1")
    seed_slots(3)

    result = race(T1, request([e1]), request([e1]))

    assert result.errors == []
    assert slots_today() == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("slot", [0, 51])
def test_i12_slot_outside_1_to_50_refused(committed_db, slot):
    with pytest.raises(IntegrityError, match="proposal_quota_slot_range"):
        with connections["owner"].cursor() as cursor:
            cursor.execute(
                "INSERT INTO proposal (id, tenant_id, requested_by, status, quota_day, quota_slot,"
                f" created_at, updated_at) VALUES (gen_random_uuid(), %s, 'c1', 'drafting',"
                f" {TODAY}, %s, now(), now())",
                [T1, slot],
            )
