from dataclasses import dataclass
from uuid import UUID, uuid5

from payables.domain.checks.check_job import MAX_BILLS


@dataclass(frozen=True)
class RecheckJob:
    id: UUID
    bill_ids: list[UUID]


def recheck_jobs(event_id: UUID, bill_ids: list[UUID]) -> list[RecheckJob]:
    # Job ids come from the event id, so a repeat delivery finds the same jobs (D42).
    batches = [bill_ids[start : start + MAX_BILLS] for start in range(0, len(bill_ids), MAX_BILLS)]
    return [RecheckJob(uuid5(event_id, str(n)), batch) for n, batch in enumerate(batches)]
