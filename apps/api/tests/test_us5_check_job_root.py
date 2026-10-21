from uuid import UUID, uuid4

import pytest

from payables.domain.checks.jobs import MAX_BILLS, CheckJob, CheckJobStatus, CheckResult
from payables.domain.errors import ValidationError

OK = CheckResult.OK
FAILED = CheckResult.FAILED


def job(bills: int) -> CheckJob:
    return CheckJob(uuid4(), CheckJobStatus.QUEUED, bills, ok_count=0, failed_count=0)


def test_us5_empty_list_refused():
    with pytest.raises(ValidationError):
        CheckJob.bills_to_check([])


def test_us5_max_500_bills():
    ids = [UUID(int=n) for n in range(MAX_BILLS + 1)]

    assert len(CheckJob.bills_to_check(ids[:MAX_BILLS])) == 500
    with pytest.raises(ValidationError):
        CheckJob.bills_to_check(ids)


def test_us5_repeated_bill_checked_once():
    b1, b2 = UUID(int=1), UUID(int=2)

    assert CheckJob.bills_to_check([b1, b2, b1]) == [b1, b2]


@pytest.mark.parametrize(
    ("results", "status", "failed"),
    [
        ([OK], CheckJobStatus.RUNNING, 0),
        ([OK, FAILED], CheckJobStatus.RUNNING, 1),
        ([OK, OK, FAILED], CheckJobStatus.COMPLETED, 1),
        ([FAILED, FAILED, OK], CheckJobStatus.COMPLETED, 2),
        ([FAILED, FAILED, FAILED], CheckJobStatus.FAILED, 3),
    ],
)
def test_us6_d41_status_after_results(results, status, failed):
    j1 = job(3)

    for result in results:
        j1.record(result)

    assert (j1.status, j1.failed_count) == (status, failed)


def test_i13_no_result_after_last_bill():
    j1 = job(1)
    j1.record(OK)

    with pytest.raises(ValueError):
        j1.record(OK)
