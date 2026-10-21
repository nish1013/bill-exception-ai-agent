import logging
from typing import Any
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import BaseChannelLayer, get_channel_layer

from payables.application.console_events import ConsoleEvent
from payables.domain.checks.jobs import BillCheckCompleted, BillCheckProgress
from payables.domain.proposals.proposals import FixProposalReady

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


def tenant_group(tenant_id: UUID) -> str:
    # A socket joins only the group of its token's tenant (D47).
    return f"tenant.{tenant_id}"


def console_event_message(event: ConsoleEvent) -> dict[str, Any]:
    match event:
        case BillCheckProgress():
            return {
                "type": "BillCheckProgress",
                "jobId": str(event.job_id),
                "seq": event.seq,
                "percent": event.percent,
            }
        case BillCheckCompleted():
            return {
                "type": "BillCheckCompleted",
                "jobId": str(event.job_id),
                "seq": event.seq,
                "status": event.status.value,
                "failedCount": event.failed_count,
            }
        case FixProposalReady():
            return {
                "type": "FixProposalReady",
                "proposalId": str(event.proposal_id),
                "status": event.status.value,
            }
