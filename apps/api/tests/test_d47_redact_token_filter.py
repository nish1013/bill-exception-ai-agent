import logging

from payables.entrypoints.ws.redact_token_filter import RedactTokenFilter


def _record(msg: str, *args) -> logging.LogRecord:
    return logging.LogRecord("uvicorn.error", logging.INFO, __file__, 1, msg, args, None)


def test_d47_uvicorn_socket_line_keeps_path_drops_token():
    record = _record('%s - "WebSocket %s" [accepted]', "127.0.0.1:1", "/ws/events/?token=a.b.c")

    RedactTokenFilter().filter(record)

    assert (
        record.getMessage() == '127.0.0.1:1 - "WebSocket /ws/events/?token=[redacted]" [accepted]'
    )


def test_d47_token_in_message_text_redacted():
    record = _record("GET /ws/events/?token=a.b.c&x=1")

    RedactTokenFilter().filter(record)

    assert record.getMessage() == "GET /ws/events/?token=[redacted]&x=1"
