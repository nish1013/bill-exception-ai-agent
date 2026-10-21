from payables.application.ports.check_job_repository import CheckJobRepository
from payables.application.ports.checked_bill_repository import CheckedBillRepository
from payables.application.ports.exception_repository import ExceptionRepository
from payables.domain.checks.bill_checks import run_rules
from payables.domain.checks.check_bill_command import CheckBill
from payables.domain.checks.check_result import CheckResult


def check_bill(
    command: CheckBill,
    bills: CheckedBillRepository,
    exceptions: ExceptionRepository,
    jobs: CheckJobRepository,
) -> None:
    if not jobs.is_pending(command.job_id, command.bill_id):
        return
    bill = bills.get(command.bill_id)
    exceptions.add_missing(bill.id, run_rules(bill, bills.earlier_alike(bill)))
    record_check_result(command, CheckResult.OK, None, jobs)


def record_check_result(
    command: CheckBill, result: CheckResult, error: str | None, jobs: CheckJobRepository
) -> None:
    job = jobs.lock(command.job_id)
    # A repeat delivery finds the result already written (D42).
    if job is None or not jobs.is_pending(command.job_id, command.bill_id):
        return
    job.record(result)
    jobs.save_result(job, command.bill_id, result, error)
