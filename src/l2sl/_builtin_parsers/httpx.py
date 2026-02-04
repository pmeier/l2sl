import logging

from structlog.typing import EventDict

from . import register_builtin_parser


@register_builtin_parser(logger="httpx")
def httpx(record: logging.LogRecord) -> EventDict:
    assert record.args is not None
    method, url, protocol, status_code, _ = record.args
    return {
        "event": "request",
        "method": method,
        "url": str(url),
        "protocol": protocol,
        "status_code": status_code,
    }
