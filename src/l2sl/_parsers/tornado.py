import logging
from typing import Any

from ._core import register_builtin_parser
from ._regexp import RegexpEventParser

tornado_access = register_builtin_parser(RegexpEventParser(), logger="tornado.access")


@tornado_access.register_event_handler(
    r"(?P<status_code>\d{3}) (?P<method>[A-Z]+) (?P<endpoint>.*) \((?P<origin>.*)\) (?P<elapsed_time>\d+\.\d+)ms"
)
def event_handler(
    groups: dict[str, str], record: logging.LogRecord
) -> tuple[str, dict[str, Any]]:
    groups["elapsed_time"] = float(groups["elapsed_time"]) * 1e-3  # type: ignore[assignment]
    return "request", groups
