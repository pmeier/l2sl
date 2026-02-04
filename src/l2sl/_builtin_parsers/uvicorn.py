import logging

from structlog.typing import EventDict

from .._parse import RegexpEventParser
from . import register_builtin_parser

uvicorn_error = register_builtin_parser(RegexpEventParser(), logger="uvicorn.error")


@uvicorn_error.register_event_handler(r"(?P<event>(Started|Finished) server process)")
def server_process(groups: dict[str, str], record: logging.LogRecord) -> EventDict:
    assert record.args is not None
    (pid,) = record.args
    return groups | {"pid": pid}


@uvicorn_error.register_event_handler(r"(?P<event>Uvicorn running) on")
def uvicorn_running(groups: dict[str, str], record: logging.LogRecord) -> EventDict:
    assert record.args is not None
    _, host, port = record.args
    return groups | {"host": host, "port": port}


@register_builtin_parser(logger="uvicorn.access")
def uvicorn_access(record: logging.LogRecord) -> EventDict:
    assert record.args is not None
    origin, method, endpoint, protocol_version, status_code = record.args
    return {
        "event": "request",
        "origin": origin,
        "method": method,
        "endpoint": endpoint,
        "protocol": f"HTTP/{protocol_version}",
        "status_code": status_code,
    }
