import logging
import re
from typing import Any

TOKEN_PARAM = re.compile(r"(token=)[^&\s\"']+")


class RedactTokenFilter(logging.Filter):
    """The socket URL carries the JWT. Server logs keep the path and drop the token."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact(arg) for arg in record.args)
        return True


def _redact(value: Any) -> Any:
    return TOKEN_PARAM.sub(r"\1[redacted]", value) if isinstance(value, str) else value
