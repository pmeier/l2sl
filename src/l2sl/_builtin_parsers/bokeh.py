import logging

from structlog.typing import EventDict

from .._parse import RegexpEventParser
from . import register_builtin_parser

bokeh_server_server = register_builtin_parser(
    RegexpEventParser(), logger="bokeh.server.server"
)


@bokeh_server_server.register_event_handler(
    r"(?P<event>Starting Bokeh server) version (?P<bokeh_version>\d+\.\d+\.\d+) \(running on Tornado (?P<tornado_version>\d+\.\d+\.\d+)\)"
)
def starting_server(groups: dict[str, str], record: logging.LogRecord) -> EventDict:
    return groups


bokeh_server_tornado = register_builtin_parser(
    RegexpEventParser(), logger="bokeh.server.tornado"
)


@bokeh_server_tornado.register_event_handler(r"\[pid \d+\] \d+ clients connected")
def clients(groups: dict[str, str], record: logging.LogRecord) -> EventDict:
    assert record.args is not None
    pid, number = record.args
    return {"event": "clients", "pid": pid, "number": number}


@bokeh_server_tornado.register_event_handler(
    r"\[pid \d+\]\s+.*? has \d+ sessions with \d+ unused"
)
def sessions(groups: dict[str, str], record: logging.LogRecord) -> EventDict:
    assert record.args is not None
    pid, endpoint, number, unused = record.args
    return {
        "event": "sessions",
        "pid": pid,
        "endpoint": endpoint,
        "number": number,
        "unused": unused,
    }
