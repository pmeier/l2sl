import logging
from typing import Any

from ._core import register_builtin_parser
from ._regexp import RegexpEventParser

panel_io = register_builtin_parser(RegexpEventParser(), logger="panel.io")


@panel_io.register_event_handler(r"(?P<event>Session) (?P<id>\d+) (?P<state>.+)")
def session(
    groups: dict[str, str], record: logging.LogRecord
) -> tuple[str, dict[str, Any]]:
    return groups.pop("event"), groups
