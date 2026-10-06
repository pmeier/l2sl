import logging

from structlog.typing import EventDict

from .._parse import RegexpEventParser, expect_tuple_args
from . import register_builtin_parser

uvicorn_error = register_builtin_parser(RegexpEventParser(), logger="uvicorn.error")


@uvicorn_error.register_event_handler(r"(?P<event>(Started|Finished) server process)")
def server_process(groups: dict[str, str], record: logging.LogRecord) -> EventDict:
    (pid,) = expect_tuple_args(record, 1)
    return groups | {"pid": pid}


@uvicorn_error.register_event_handler(r"(?P<event>Uvicorn running) on")
def uvicorn_running(groups: dict[str, str], record: logging.LogRecord) -> EventDict:
    _, host, port = expect_tuple_args(record, 3)
    return groups | {"host": host, "port": port}


@register_builtin_parser(logger="uvicorn.access")
def uvicorn_access(record: logging.LogRecord) -> EventDict:
    origin, method, endpoint, protocol_version, status_code = expect_tuple_args(record, 5)
    return {
        "event": "request",
        "origin": origin,
        "method": method,
        "endpoint": endpoint,
        "protocol": f"HTTP/{protocol_version}",
        "status_code": status_code,
    }
