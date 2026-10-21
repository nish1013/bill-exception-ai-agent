from payables.application.ports.check_job_repository import CheckJobRepository
from payables.application.ports.checked_bill_repository import CheckedBillRepository
from payables.application.ports.exception_repository import ExceptionRepository
from payables.application.ports.purchase_order_repository import PurchaseOrderRepository
from payables.application.ports.resolution_repository import ResolutionRepository
from payables.domain.checks.bill_checks import run_rules
from payables.domain.checks.check_bill_command import CheckBill
from payables.domain.checks.check_job import CheckJob
from payables.domain.checks.check_result import CheckResult
from payables.domain.checks.checked_bill import CheckedBill
from payables.domain.checks.exception_changes import changes_after_check
from payables.domain.purchase_order import PurchaseOrder


def check_bill(
    command: CheckBill,
    bills: CheckedBillRepository,
    purchase_orders: PurchaseOrderRepository,
    exceptions: ExceptionRepository,
    resolutions: ResolutionRepository,
    jobs: CheckJobRepository,
) -> CheckJob | None:
    if not jobs.is_pending(command.job_id, command.bill_id):
        return None
    bill = bills.get(command.bill_id)
    findings = run_rules(bill, bills.earlier_alike(bill), _purchase_order(bill, purchase_orders))
    exceptions.add_missing(bill.id, findings)
    changes = changes_after_check(findings, exceptions.on_bill(bill.id))
    resolutions.resolve_by_system(changes.to_resolve)
    resolutions.reopen(changes.to_reopen)
    return record_check_result(command, CheckResult.OK, None, jobs)


def record_check_result(
    command: CheckBill, result: CheckResult, error: str | None, jobs: CheckJobRepository
) -> CheckJob | None:
    job = jobs.lock(command.job_id)
    # A repeat delivery finds the result already written (D42).
    if job is None or not jobs.is_pending(command.job_id, command.bill_id):
        return None
    job.record(result)
    jobs.save_result(job, command.bill_id, result, error)
    return job


def _purchase_order(
    bill: CheckedBill, purchase_orders: PurchaseOrderRepository
) -> PurchaseOrder | None:
    return None if bill.po_number is None else purchase_orders.find(bill.po_number)
