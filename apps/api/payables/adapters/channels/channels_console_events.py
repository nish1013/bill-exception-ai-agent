import logging
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import BaseChannelLayer, get_channel_layer

from payables.adapters.channels.console_event_message import console_event_message
from payables.adapters.channels.tenant_group import tenant_group
from payables.application.checks import ConsoleEvent

logger = logging.getLogger(__name__)

CONSOLE_EVENT = "console.event"


class ChannelsConsoleEvents:
    def __init__(self, layer: BaseChannelLayer | None = None) -> None:
        self._layer = layer or get_channel_layer()

    def publish(self, tenant_id: UUID, event: ConsoleEvent) -> None:
        message = {"type": CONSOLE_EVENT, "event": console_event_message(event)}
        try:
            async_to_sync(self._layer.group_send)(tenant_group(tenant_id), message)
        except Exception:
            # The job row holds the result. The board reads it when its socket reconnects (D18).
            logger.warning("console event not sent: %s", message["event"], exc_info=True)
