import json
from collections.abc import Sequence
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from payables.application.proposals import LlmPort
from payables.domain.proposals.agent import (
    MAX_TOOL_CALLS,
    MessageRole,
    ModelMessage,
    ModelReply,
    ToolCall,
    ToolSpec,
)

STUB = "stub"
RULE_TOOLS = {
    "duplicate": "draft_hold",
    "possible_duplicate": "draft_hold",
    "po_mismatch": "draft_hold",
    "missing_vat": "draft_credit",
    "missing_receipt": "draft_hold",
}


class StubLlm:
    """A model with no network call: it lists the exceptions, then drafts one action per bill."""

    def complete(
        self, messages: Sequence[ModelMessage], tools: Sequence[ToolSpec], timeout_seconds: float
    ) -> ModelReply:
        if _drafted(messages):
            return ModelReply("The plan is drafted.")
        listed = _listed_exceptions(messages)
        if listed is None:
            return ModelReply("", (ToolCall("call_1", "list_exceptions", {}),))
        calls: list[ToolCall] = []
        for exception in listed:
            bill_id = exception["bill_id"]
            if any(call.arguments.get("bill_id") == bill_id for call in calls):
                continue
            tool = RULE_TOOLS.get(exception["rule"], "draft_hold")
            calls.append(ToolCall(f"call_{len(calls) + 2}", tool, {"bill_id": bill_id}))
        return ModelReply("", tuple(calls[: MAX_TOOL_CALLS - 1]))


def llm_from_settings() -> LlmPort:
    if settings.LLM_PROVIDER == STUB:
        return StubLlm()
    raise ImproperlyConfigured(f"LLM_PROVIDER {settings.LLM_PROVIDER!r} is not known")


def _listed_exceptions(messages: Sequence[ModelMessage]) -> list[dict[str, Any]] | None:
    for message in messages:
        if message.role is MessageRole.TOOL:
            content = json.loads(message.content)
            if content.get("tool") == "list_exceptions":
                return content.get("exceptions", [])
    return None


def _drafted(messages: Sequence[ModelMessage]) -> bool:
    return any(
        message.role is MessageRole.TOOL
        and json.loads(message.content).get("tool", "").startswith("draft_")
        for message in messages
    )
