from dataclasses import dataclass

from payables.adapters.broker.queues import CHECKS


@dataclass(frozen=True)
class Route:
    task: str
    queue: str


CHECK_BILL_TASK = "payables.check_bill"

ROUTES: dict[str, Route] = {
    "CheckBill": Route(CHECK_BILL_TASK, CHECKS),
}
