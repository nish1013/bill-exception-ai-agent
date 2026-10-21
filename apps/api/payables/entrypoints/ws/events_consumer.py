import logging
import time
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from jwt import PyJWKClientConnectionError

from payables.adapters.channels import tenant_group
from payables.adapters.identity import (
    InvalidTokenError,
    principal_from_claims,
    verifier_from_settings,
)

logger = logging.getLogger(__name__)

TOKEN_EXPIRED = 4401


def now() -> float:
    return time.time()


class EventsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        self._group: str | None = None
        try:
            claims = await sync_to_async(verifier_from_settings().verify)(self._token())
            tenant_id: UUID = principal_from_claims(claims).tenant_id
        except InvalidTokenError as error:
            logger.info("socket token refused: %s", error)
            await self.close()
            return
        except PyJWKClientConnectionError:
            logger.warning("socket refused: the signing keys are not reachable", exc_info=True)
            await self.close()
            return
        self._expires_at = int(claims["exp"])
        self._group = tenant_group(tenant_id)
        await self.channel_layer.group_add(self._group, self.channel_name)
        await self.accept()

    async def disconnect(self, code: int) -> None:
        if self._group is not None:
            await self.channel_layer.group_discard(self._group, self.channel_name)

    async def receive_json(self, content: Any, **kwargs) -> None:
        pass

    async def console_event(self, message: dict[str, Any]) -> None:
        # A socket outlives its token. It carries no event after the token expires.
        if now() >= self._expires_at:
            await self.close(code=TOKEN_EXPIRED)
            return
        await self.send_json(message["event"])

    def _token(self) -> str:
        query = parse_qs(self.scope.get("query_string", b"").decode())
        token = (query.get("token") or [""])[0].strip()
        if not token:
            raise InvalidTokenError("no token")
        return token
