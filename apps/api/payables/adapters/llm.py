import json
from collections.abc import Sequence
from typing import Any

import httpx
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallUnion,
    ChatCompletionToolParam,
)

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
OPENAI = "openai"
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


class OpenAiLlm:
    """The OpenAI chat model. It gets only the tools it is given, and it never retries a call."""

    def __init__(self, api_key: str, model: str, http_client: httpx.Client | None = None) -> None:
        # The draft task retries a failed call. A retry here can pass the 60 s bound (D20).
        self._client = OpenAI(api_key=api_key, max_retries=0, http_client=http_client)
        self._model = model

    def complete(
        self, messages: Sequence[ModelMessage], tools: Sequence[ToolSpec], timeout_seconds: float
    ) -> ModelReply:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[_openai_message(message) for message in messages],
            tools=[_openai_tool(tool) for tool in tools],
            timeout=timeout_seconds,
        )
        reply = response.choices[0].message
        content = reply.content or reply.refusal or ""
        return ModelReply(content, tuple(_tool_call(call) for call in reply.tool_calls or ()))


def llm_from_settings() -> LlmPort:
    if settings.LLM_PROVIDER == STUB:
        return StubLlm()
    if settings.LLM_PROVIDER == OPENAI:
        if not settings.OPENAI_API_KEY:
            raise ImproperlyConfigured("LLM_PROVIDER openai needs OPENAI_API_KEY")
        return OpenAiLlm(settings.OPENAI_API_KEY, settings.LLM_MODEL)
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


def _openai_message(message: ModelMessage) -> ChatCompletionMessageParam:
    if message.role is MessageRole.SYSTEM:
        return {"role": "system", "content": message.content}
    if message.role is MessageRole.USER:
        return {"role": "user", "content": message.content}
    if message.role is MessageRole.TOOL:
        return {
            "role": "tool",
            "content": message.content,
            "tool_call_id": message.tool_call_id or "",
        }
    if not message.tool_calls:
        return {"role": "assistant", "content": message.content}
    return {
        "role": "assistant",
        "content": message.content or None,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in message.tool_calls
        ],
    }


def _openai_tool(tool: ToolSpec) -> ChatCompletionToolParam:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _tool_call(call: ChatCompletionMessageToolCallUnion) -> ToolCall:
    # A custom tool call names a tool that was never sent, so the allowlist refuses it.
    if call.type == "custom":
        return ToolCall(call.id, call.custom.name, {})
    return ToolCall(call.id, call.function.name, _arguments(call.function.arguments))


def _arguments(raw: str) -> dict[str, Any]:
    # Arguments that are not a JSON object reach the tool as none, and the tool refuses the call.
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
