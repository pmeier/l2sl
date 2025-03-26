import logging
from typing import Any, cast

from ._core import register_builtin_parser
from ._regexp import RegexpEventParser

tornado_access = register_builtin_parser(RegexpEventParser(), logger="tornado.access")


@tornado_access.register_event_handler(
    r"(?P<status_code>\d{3}) (?P<method>[A-Z]+) (?P<endpoint>.*) \((?P<origin>.*)\) (?P<elapsed_time>\d+\.\d+)ms"
)
def event_handler(
    groups: dict[str, str], record: logging.LogRecord
) -> tuple[str, dict[str, Any]]:
    values = cast(dict[str, Any], groups)
    values["elapsed_time"] = float(values["elapsed_time"]) * 1e-3
    return "request", groups
