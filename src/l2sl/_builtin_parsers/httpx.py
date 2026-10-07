import logging

from structlog.typing import EventDict

from .._parse import expect_tuple_args
from . import register_builtin_parser


@register_builtin_parser(logger="httpx")
def httpx(record: logging.LogRecord) -> EventDict:
    method, url, protocol, status_code, _ = expect_tuple_args(record, 5)
    return {
        "event": "request",
        "method": method,
        "url": str(url),
        "protocol": protocol,
        "status_code": status_code,
    }
