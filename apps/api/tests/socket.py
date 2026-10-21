import json
from typing import Any

from asgiref.testing import ApplicationCommunicator

from config.asgi import application

# channels.testing needs daphne. The tests drive the ASGI socket protocol directly instead.


class EventsSocket(ApplicationCommunicator):
    def __init__(self, token: str | None) -> None:
        query = b"" if token is None else f"token={token}".encode()
        scope = {"type": "websocket", "path": "/ws/events/", "query_string": query, "headers": []}
        super().__init__(application, scope)

    async def connect(self, timeout: float = 5) -> bool:
        await self.send_input({"type": "websocket.connect"})
        return (await self.receive_output(timeout))["type"] == "websocket.accept"

    async def receive_json_from(self, timeout: float = 5) -> Any:
        message = await self.receive_output(timeout)
        assert message["type"] == "websocket.send", message
        return json.loads(message["text"])

    async def disconnect(self, code: int = 1000, timeout: float = 5) -> None:
        await self.send_input({"type": "websocket.disconnect", "code": code})
        await self.wait(timeout)


def events_socket(token: str | None) -> EventsSocket:
    return EventsSocket(token)
