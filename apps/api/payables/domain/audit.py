from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AuditKind(StrEnum):
    MODEL_INPUT = "model_input"
    MODEL_OUTPUT = "model_output"
    TOOL_CALL = "tool_call"
    DRAFT_RESULT = "draft_result"


@dataclass(frozen=True)
class AuditEntry:
    kind: AuditKind
    actor: str
    payload: dict[str, Any]
