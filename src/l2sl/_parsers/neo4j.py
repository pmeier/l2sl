import dataclasses
import logging
from typing import Any, Callable, Literal

from ._core import register_builtin_parser
from ._regexp import RegexpEventParser

neo4j = register_builtin_parser(RegexpEventParser(), logger="neo4j")


@dataclasses.dataclass(kw_only=True, frozen=True)
class Neo4jEventData:
    actor: Literal["client", "server"] | None
    event: str
    message: str
    args: tuple[Any, ...]


Neo4jEventHandler = Callable[[Neo4jEventData], tuple[str, dict[str, Any]]]


def register_neo4j_event_handler(
    event_pattern: str,
) -> Callable[[Neo4jEventHandler], Neo4jEventHandler]:
    def decorator(neo4j_event_handler: Neo4jEventHandler) -> Neo4jEventHandler:
        @neo4j.register_event_handler(
            rf"^\[#[0-9A-F]{{4}}\]\s+(?P<actor>[_CS]):\s+(?P<event>{event_pattern})\s*(?P<message>.*?)\s*$"
        )
        def regexp_event_handler(
            groups: dict[str, str], record: logging.LogRecord
        ) -> tuple[str, dict[str, Any]]:
            return neo4j_event_handler(
                Neo4jEventData(
                    actor={
                        "_": None,
                        "C": "client",
                        "S": "server",
                    }[groups["actor"]],
                    event=groups["event"].strip("<>").lower(),
                    message=groups["message"],
                    args=record.args or (),
                )
            )

        return neo4j_event_handler

    return decorator


@register_neo4j_event_handler("<POOL>")
def pool(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    if data.message.startswith("created"):
        (ip_address,) = data.args
        return "pool created", {"host": ip_address.host, "port": ip_address.port}
    elif data.message.startswith("acquire"):
        event = data.message.split(",")[0]
        access_mode, database = data.args
        return event, {
            "access_mode": access_mode,
            "database": database.name,
            "guessed": database.guessed,
        }
    elif data.message.startswith("released"):
        _, connection_id = data.args
        return "connection released", {"connection_id": connection_id}
    elif data.message.startswith("picked existing connection"):
        _, connection_id = data.args
        return "picked existing connection", {"connection_id": connection_id}
    elif data.message.startswith("checked re_auth"):
        _, auth, updated, force = data.args
        return "checked authentication", {
            "auth": auth,
            "updated": updated,
            "force": force,
        }
    elif data.message == "close":
        return "pool closed", {}
    else:
        return data.message, {}


@register_neo4j_event_handler("<RESOLVE>")
def resolve(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    if "in" in data.message:
        event = "resolving"
    elif "out" in data.message:
        event = "resolved"
    else:
        return data.message, {}

    (ip_address,) = data.args
    return event, {"host": ip_address.host, "port": ip_address.port}


@register_neo4j_event_handler("<WORKSPACE>")
def workspace(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    event = data.message.split(":")[0]
    (database,) = data.args
    return event, {"database": database}


@register_neo4j_event_handler("<OPEN>")
def open(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    (ip_address,) = data.args
    return "open connection", {"host": ip_address.host, "port": ip_address.port}


@register_neo4j_event_handler("<MAGIC>")
def magic(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    return "magic preamble", {"value": data.message}


@register_neo4j_event_handler("<HANDSHAKE>")
def handshake(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    return data.event, {"actor": data.actor, "values": data.message}


@register_neo4j_event_handler("HELLO")
def hello(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    _, values = data.args
    return "hello", values


@register_neo4j_event_handler("<CONNECTION>")
def connection(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    actor, _ = data.message.split(maxsplit=1)
    _, old, new = data.args
    return "state change", {"actor": actor, "old": old.lower(), "new": new.lower()}


@register_neo4j_event_handler("LOGON|SUCCESS|FAILURE")
def logon(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    _, values = data.args
    return data.event, {"actor": data.actor, **values}


@register_neo4j_event_handler("GOODBYE")
def goodbye(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    return "goodbye", {}


@register_neo4j_event_handler("<(CLOSE|KILL)>")
def close(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    return f"{data.event} connection", {}


@register_neo4j_event_handler("<ERROR>")
def error(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    type, message = data.args
    return data.event, {"actor": data.actor, "type": type, "message": message}


@register_neo4j_event_handler("<CONNECTION FAILED>")
def connection_failed(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    _, ip_address, message = data.args
    return data.event, {"host": ip_address.host, "port": ip_address.port}


@register_neo4j_event_handler("<OPEN FAILED>")
def open_failed(data: Neo4jEventData) -> tuple[str, dict[str, Any]]:
    _, exc = data.args
    return data.event, {"type": type(exc).__name__, "message": exc.message}
