import logging
from typing import Any

from ._core import register_builtin_parser
from ._regexp import RegexpEventParser

httpx = register_builtin_parser("httpx", RegexpEventParser())


@httpx.register_event_handler(r".*")
def server_started_process(
    groups: dict[str, str], record: logging.LogRecord
) -> tuple[str, dict[str, Any]]:
    assert record.args is not None
    method, url, protocol, status_code, _ = record.args
    return "request", {
        "method": method,
        "url": str(url),
        "protocol": protocol,
        "status_code": status_code,
    }
