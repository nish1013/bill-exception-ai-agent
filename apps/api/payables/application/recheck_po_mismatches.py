from payables.application.ports.check_job_repository import CheckJobRepository
from payables.application.ports.exception_repository import ExceptionRepository
from payables.application.ports.outbox import Outbox
from payables.domain.access import SYSTEM_ACTOR
from payables.domain.checks.jobs import CheckBill, recheck_jobs
from payables.domain.checks.rules import Rule
from payables.domain.purchase_orders import PurchaseOrderAdded


def recheck_po_mismatches(
    event: PurchaseOrderAdded,
    exceptions: ExceptionRepository,
    jobs: CheckJobRepository,
    outbox: Outbox,
) -> int:
    bill_ids = exceptions.bills_with_open(Rule.PO_MISMATCH, event.po_number)
    planned = recheck_jobs(event.event_id, bill_ids)
    if not planned or jobs.find(planned[0].id) is not None:
        return 0
    for job in planned:
        jobs.add(SYSTEM_ACTOR, job.bill_ids, job.id)
        outbox.add([CheckBill(event.tenant_id, job.id, bill_id) for bill_id in job.bill_ids])
    return len(bill_ids)
