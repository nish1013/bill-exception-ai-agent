from uuid import UUID

from payables.application.ports.check_job_repository import CheckJobRepository
from payables.domain.checks.jobs import CheckJob
from payables.domain.errors import NotFoundError


def get_check_job(job_id: UUID, jobs: CheckJobRepository) -> CheckJob:
    job = jobs.find(job_id)
    if job is None:
        raise NotFoundError("check job not found")
    return job
