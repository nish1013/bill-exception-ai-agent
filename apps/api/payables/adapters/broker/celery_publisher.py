from typing import Any
from uuid import UUID

from celery import Celery

from payables.adapters.broker.routes import ROUTES


class CeleryPublisher:
    def __init__(self, app: Celery) -> None:
        self._app = app

    def publish(self, message_id: UUID, command: str, payload: dict[str, Any]) -> None:
        route = ROUTES[command]
        # The broker transport confirms each publish before this returns (D43).
        self._app.send_task(route.task, kwargs=payload, queue=route.queue, task_id=str(message_id))
