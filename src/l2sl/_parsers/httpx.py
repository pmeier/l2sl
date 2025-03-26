import logging
from typing import Any

from ._core import register_builtin_parser


@register_builtin_parser(logger="httpx")
def httpx(event: str, record: logging.LogRecord) -> tuple[str, dict[str, Any]]:
    assert record.args is not None
    method, url, protocol, status_code, _ = record.args
    return "request", {
        "method": method,
        "url": str(url),
        "protocol": protocol,
        "status_code": status_code,
    }
