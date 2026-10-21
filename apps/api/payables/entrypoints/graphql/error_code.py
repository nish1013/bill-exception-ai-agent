from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCode:
    code: str
    status: int
