from typing import Any, Protocol
from uuid import UUID


class Publisher(Protocol):
    def publish(self, message_id: UUID, command: str, payload: dict[str, Any]) -> None: ...
