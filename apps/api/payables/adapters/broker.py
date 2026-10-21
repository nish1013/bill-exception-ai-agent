from dataclasses import dataclass
from typing import Any
from uuid import UUID

from celery import Celery
from kombu import Connection, Exchange, Queue

CHECKS = "checks"
DEAD_LETTER_SUFFIX = ".dlq"

CHECK_BILL_TASK = "payables.check_bill"
PURCHASE_ORDER_ADDED_TASK = "payables.purchase_order_added"


@dataclass(frozen=True)
class Route:
    task: str
    queue: str


ROUTES: dict[str, Route] = {
    "CheckBill": Route(CHECK_BILL_TASK, CHECKS),
    "PurchaseOrderAdded": Route(PURCHASE_ORDER_ADDED_TASK, CHECKS),
}


class CeleryPublisher:
    def __init__(self, app: Celery) -> None:
        self._app = app

    def publish(self, message_id: UUID, command: str, payload: dict[str, Any]) -> None:
        route = ROUTES[command]
        # The broker transport confirms each publish before this returns (D43).
        self._app.send_task(route.task, kwargs=payload, queue=route.queue, task_id=str(message_id))


def dead_letter_name(queue: str) -> str:
    return f"{queue}{DEAD_LETTER_SUFFIX}"


def work_queue(name: str) -> Queue:
    # A rejected message goes to <queue>.dlq through the default exchange (D17, D43).
    return Queue(
        name,
        Exchange(name, type="direct"),
        routing_key=name,
        durable=True,
        queue_arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": dead_letter_name(name),
        },
    )


def dead_letter_queue(name: str) -> Queue:
    dead_letters = dead_letter_name(name)
    return Queue(dead_letters, Exchange(dead_letters, type="direct"), routing_key=dead_letters)


WORK_QUEUES = (work_queue(CHECKS),)
DEAD_LETTER_QUEUES = (dead_letter_queue(CHECKS),)
ALL_QUEUES = WORK_QUEUES + DEAD_LETTER_QUEUES


def declare_queues(connection: Connection) -> None:
    # RabbitMQ drops a rejected message when its dead-letter queue does not exist yet.
    channel = connection.default_channel
    for queue in ALL_QUEUES:
        queue.bind(channel).declare()
