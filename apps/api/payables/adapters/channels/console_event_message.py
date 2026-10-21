from typing import Any

from payables.application.checks import ConsoleEvent
from payables.domain.checks.jobs import BillCheckCompleted, BillCheckProgress


def console_event_message(event: ConsoleEvent) -> dict[str, Any]:
    match event:
        case BillCheckProgress():
            return {
                "type": "BillCheckProgress",
                "jobId": str(event.job_id),
                "seq": event.seq,
                "percent": event.percent,
            }
        case BillCheckCompleted():
            return {
                "type": "BillCheckCompleted",
                "jobId": str(event.job_id),
                "seq": event.seq,
                "status": event.status.value,
                "failedCount": event.failed_count,
            }
