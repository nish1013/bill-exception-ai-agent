import json
from pathlib import Path
from typing import Any

import httpx
import openai
import pytest
from django.core.exceptions import ImproperlyConfigured

from payables.adapters.llm import OpenAiLlm, StubLlm, llm_from_settings
from payables.application.proposals import run_agent
from payables.domain.audit import AuditKind
from payables.domain.proposals.agent import ALLOWED_TOOLS, TOOL_SPECS, DraftOutcome
from payables.domain.proposals.proposals import ActionKind, DraftAction
from tests.proposal_data import SCOPE_B2, duplicate_scope

RECORDING = json.loads(
    (Path(__file__).parent / "recordings" / "openai_chat_completions.json").read_text()
)
MODEL = "gpt-4.1-mini-2025-04-14"
TEST_KEY = "test-key-not-real"


class RecordedOpenAi:
    """Answers each request with the next recorded response, and keeps each request."""

    def __init__(self, *responses: dict[str, Any] | int) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def llm(self) -> OpenAiLlm:
        return OpenAiLlm(TEST_KEY, MODEL, httpx.Client(transport=httpx.MockTransport(self._answer)))

    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(request.content) for request in self.requests]

    def _answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, int):
            return httpx.Response(response, json={"error": {"message": "recorded error"}})
        return httpx.Response(200, json=response)


def _hold_run() -> RecordedOpenAi:
    return RecordedOpenAi(RECORDING["list_exceptions"], RECORDING["draft_hold"], RECORDING["final"])


def _no_time_passes() -> float:
    return 0.0


def _tool_outcomes(outcome: DraftOutcome) -> list[tuple[str, str]]:
    return [
        (entry.payload["name"], entry.payload["outcome"])
        for entry in outcome.audit
        if entry.kind is AuditKind.TOOL_CALL
    ]


def _with_arguments(arguments: str) -> dict[str, Any]:
    response = json.loads(json.dumps(RECORDING["draft_hold"]))
    response["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = arguments
    return response


@pytest.mark.parametrize("adapter", ["stub", "openai"])
def test_d54_both_adapters_draft_hold_on_b2(adapter):
    llm = StubLlm() if adapter == "stub" else _hold_run().llm()

    outcome = run_agent(duplicate_scope(), llm, _no_time_passes)

    assert (outcome.actions, outcome.failed_reason) == (
        [DraftAction(ActionKind.HOLD, SCOPE_B2)],
        None,
    )
    assert _tool_outcomes(outcome) == [("list_exceptions", "done"), ("draft_hold", "done")]


def test_d54_openai_request_has_pinned_model_allowlist_and_bound():
    recorded = _hold_run()

    run_agent(duplicate_scope(), recorded.llm(), _no_time_passes)

    first = recorded.bodies()[0]
    assert first["model"] == MODEL
    assert [tool["function"]["name"] for tool in first["tools"]] == [s.name for s in TOOL_SPECS]
    assert {tool["type"] for tool in first["tools"]} == {"function"}
    assert recorded.requests[0].headers["authorization"] == f"Bearer {TEST_KEY}"
    assert recorded.requests[0].extensions["timeout"]["read"] == 60.0


def test_d54_openai_messages_carry_tool_call_ids():
    recorded = _hold_run()

    run_agent(duplicate_scope(), recorded.llm(), _no_time_passes)

    messages = recorded.bodies()[1]["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool"]
    call = messages[2]["tool_calls"][0]
    assert (call["function"]["name"], call["function"]["arguments"]) == ("list_exceptions", "{}")
    assert messages[3]["tool_call_id"] == call["id"]
    assert json.loads(messages[3]["content"])["exceptions"][0]["bill_id"] == str(SCOPE_B2)


def test_d54_openai_approve_call_refused_only_hold_drafted():
    recorded = RecordedOpenAi(RECORDING["approve_and_hold"], RECORDING["final"])

    outcome = run_agent(duplicate_scope(), recorded.llm(), _no_time_passes)

    assert _tool_outcomes(outcome) == [("approve_fix_proposal", "refused"), ("draft_hold", "done")]
    assert outcome.actions == [DraftAction(ActionKind.HOLD, SCOPE_B2)]
    refused = json.loads(recorded.bodies()[1]["messages"][3]["content"])
    assert refused["outcome"] == "refused"


@pytest.mark.parametrize("arguments", ['{"bill_id": ', "[1]", '"text"'])
def test_d54_openai_arguments_not_an_object_give_invalid_call(arguments):
    recorded = RecordedOpenAi(_with_arguments(arguments), RECORDING["final"])

    outcome = run_agent(duplicate_scope(), recorded.llm(), _no_time_passes)

    assert _tool_outcomes(outcome) == [("draft_hold", "invalid")]
    assert outcome.actions == []


def test_d54_openai_error_raises_after_one_request():
    recorded = RecordedOpenAi(500, RECORDING["final"])

    with pytest.raises(openai.InternalServerError):
        run_agent(duplicate_scope(), recorded.llm(), _no_time_passes)
    assert len(recorded.requests) == 1


@pytest.mark.parametrize(
    ("provider", "key", "expected"),
    [
        ("stub", "", StubLlm),
        ("stub", TEST_KEY, StubLlm),
        ("openai", TEST_KEY, OpenAiLlm),
        ("openai", "", ImproperlyConfigured),
        ("claude", TEST_KEY, ImproperlyConfigured),
    ],
)
def test_d54_llm_provider_picks_the_adapter(settings, provider, key, expected):
    settings.LLM_PROVIDER, settings.OPENAI_API_KEY = provider, key

    if expected is ImproperlyConfigured:
        with pytest.raises(ImproperlyConfigured):
            llm_from_settings()
    else:
        assert isinstance(llm_from_settings(), expected)


def test_d54_recording_holds_only_allowlisted_tools_and_no_secrets():
    text = json.dumps(RECORDING)
    names = {
        call["function"]["name"]
        for response in RECORDING.values()
        for call in response["choices"][0]["message"].get("tool_calls") or []
    }
    assert names - ALLOWED_TOOLS == {"approve_fix_proposal"}
    assert "sk-" not in text and "org-" not in text
