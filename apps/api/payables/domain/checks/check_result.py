from enum import StrEnum


class CheckResult(StrEnum):
    PENDING = "pending"
    OK = "ok"
    FAILED = "failed"
