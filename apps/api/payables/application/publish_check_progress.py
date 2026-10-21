from uuid import UUID

from payables.application.ports.console_events import ConsoleEvents
from payables.domain.checks.check_job import CheckJob


def publish_check_progress(tenant_id: UUID, job: CheckJob, events: ConsoleEvents) -> None:
    for event in job.progress_events():
        events.publish(tenant_id, event)
