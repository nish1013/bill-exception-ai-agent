from uuid import uuid4

import pytest

from payables.domain.checks.jobs import (
    BillCheckCompleted,
    BillCheckProgress,
    CheckJob,
    CheckJobStatus,
    CheckResult,
)

J1 = uuid4()


def _job(bill_count: int) -> CheckJob:
    return CheckJob(J1, CheckJobStatus.QUEUED, bill_count, ok_count=0, failed_count=0)


@pytest.mark.parametrize(
    ("bill_count", "checked", "percent"),
    [(5, 0, 0), (5, 2, 40), (7, 3, 42), (3, 2, 66), (3, 3, 100)],
)
def test_us7_percent_rounds_down(bill_count, checked, percent):
    job = _job(bill_count)
    for _ in range(checked):
        job.record(CheckResult.OK)

    assert (job.seq, job.percent) == (checked, percent)


def test_d19_seq_goes_up_by_one_per_result():
    job = _job(3)
    seqs = []
    for result in (CheckResult.OK, CheckResult.FAILED, CheckResult.OK):
        job.record(result)
        seqs.append(job.seq)

    assert seqs == [1, 2, 3]


def test_us7_running_job_gives_progress_only():
    job = _job(5)
    job.record(CheckResult.OK)
    job.record(CheckResult.OK)

    assert job.progress_events() == [BillCheckProgress(J1, 2, 40)]


def test_us7_last_result_gives_progress_then_completed():
    job = _job(2)
    job.record(CheckResult.OK)
    job.record(CheckResult.FAILED)

    assert job.progress_events() == [
        BillCheckProgress(J1, 2, 100),
        BillCheckCompleted(J1, 2, CheckJobStatus.COMPLETED, failed_count=1),
    ]


def test_d41_all_failed_completes_as_failed():
    job = _job(1)
    job.record(CheckResult.FAILED)

    assert job.progress_events()[-1] == BillCheckCompleted(
        J1, 1, CheckJobStatus.FAILED, failed_count=1
    )
