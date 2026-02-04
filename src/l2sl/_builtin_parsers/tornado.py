import logging

from structlog.typing import EventDict

from .._parse import RegexpEventParser
from . import register_builtin_parser

tornado_access = register_builtin_parser(RegexpEventParser(), logger="tornado.access")


@tornado_access.register_event_handler(
    r"(?P<status_code>\d{3}) (?P<method>[A-Z]+) (?P<endpoint>.*) \((?P<origin>.*)\) (?P<elapsed_time>\d+\.\d+)ms"
)
def event_handler(groups: dict[str, str], record: logging.LogRecord) -> EventDict:
    return {
        "event": "request",
        "elapsed_time": float(groups.pop("elapsed_time")) * 1e-3,
    } | groups
