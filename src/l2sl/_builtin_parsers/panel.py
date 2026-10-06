import logging

from structlog.typing import EventDict

from .._parse import RegexpEventParser, expect_tuple_args
from . import register_builtin_parser

panel_io = register_builtin_parser(RegexpEventParser(), logger="panel.io")


@panel_io.register_event_handler(r"(?P<event>Session) (?P<id>\d+) (?P<state>.+)")
def session(groups: dict[str, str], record: logging.LogRecord) -> EventDict:
    return groups


panel_viewable = register_builtin_parser(RegexpEventParser(), logger="panel.viewable")


@panel_viewable.register_event_handler(r"Session \d+ (?P<event>(received|finished processing) events)")
def handler(groups: dict[str, str], record: logging.LogRecord) -> EventDict:
    session_id, events = expect_tuple_args(record, 2)
    return {"event": groups["event"], "sesion_id": session_id, "events": events}
