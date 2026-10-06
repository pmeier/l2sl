from __future__ import annotations

__all__ = [
    "Parser",
    "safe_fallback_parser",
    "RegexpEventParser",
    "RegexpEventHandler",
    "exc_to_exc_info",
]

import functools
import logging
import re
import secrets
import sys
from typing import Any, Callable, cast

from structlog.typing import EventDict, ExcInfo

Parser = Callable[[logging.LogRecord], EventDict]
"""Parses a stdlib [logging.LogRecord][] into a [structlog.typing.EventDict][].

A parser may raise [structlog.exceptions.DropEvent][] to discard a record.
"""

_DEFAULT_RECORD_ATTRIBUTES = set(logging.LogRecord("", logging.DEBUG, "", 0, "", None, None).__dict__.keys())


def exc_to_exc_info(exc_info: Any) -> ExcInfo:
    if isinstance(exc_info, BaseException):
        return (type(exc_info), exc_info, exc_info.__traceback__)
    if isinstance(exc_info, tuple):
        return exc_info
    return cast(ExcInfo, sys.exc_info())


def _extract_record_extra(record: logging.LogRecord) -> dict[str, Any]:
    return {k: v for k, v in record.__dict__.items() if k not in _DEFAULT_RECORD_ATTRIBUTES}


def safe_fallback_parser(record: logging.LogRecord) -> EventDict:
    """Safe fallback parser that turns a [logging.LogRecord][] into a minimal [structlog.typing.EventDict][].

    The formatted log message becomes the `event` key and any values passed through the record's `extra` attribute are
    included. `exc_info` is normalized to the tuple form [structlog][] expects.

    This parser is safe and will always produce a valid [structlog.typing.EventDict][]. In case of unexpected errors, a
    `l2sl_safe_fallback_parser_errors` key will be included in the returned event dict containing a human-readable list
    of error messages. In these cases parsing happens on a best-effort basis and diverges from the format explained
    above.

    Args:
        record: The stdlib [logging.LogRecord][] to parse.

    Returns:
        The [structlog.typing.EventDict][] for the record.
    """
    errors: list[str] = []
    try:
        event_dict = _extract_record_extra(record)
        if "level" in event_dict:
            # "level" can be put into the extras of a stdlib record, but is reserved when logging with structlog
            event_dict["extra_level"] = event_dict.pop("level")
            errors.append("Reserved key 'level' in record extras. Moved to the 'extra_level' key.")

        try:
            event_dict |= {"event": record.getMessage()}
        except Exception:
            event_dict |= {
                "event": "unable to format record message",
                "record_msg": record.msg,
                "record_args": record.args,
            }
            errors.append(
                "Unable to format record message. Format message moved to 'record_msg' key and format arguments to "
                "'record_args' key."
            )

        if exc_info := record.exc_info:
            event_dict["exc_info"] = exc_to_exc_info(exc_info)

        if stack_info := record.stack_info:
            event_dict["stack_info"] = stack_info
    except Exception as exc:
        # This should never happen, but we need to make sure to never break the promise of not raising.
        # The record itself is deliberately excluded as downstream renderers may choke on arbitrary
        # objects held in it, and the exc_info traceback already identifies the failure.
        event_dict = {"event": "unknown event", "exc_info": exc_to_exc_info(exc)}
        errors.append("Unknown parsing error.")
    finally:
        if errors:
            event_dict["l2sl_safe_fallback_parser_errors"] = errors

    return event_dict


RegexpEventHandler = Callable[[dict[str, str], logging.LogRecord], EventDict]
"""Builds a [structlog.typing.EventDict][] from a matched log message.

Handlers receive the named groups captured by the regexp as a dict, together with the original stdlib
[logging.LogRecord][].
"""


class RegexpEventParser:
    """A [l2sl.Parser][] that routes log messages to event handlers based on regexp matches.

    Event handlers are registered with [l2sl.RegexpEventParser.register_event_handler][]. Before the first call, all
    registered patterns are compiled into a single alternation. Messages that match no pattern are passed to the
    fallback parser.

    Args:
        fallback: Parser used when no registered pattern matches.
    """

    def __init__(self, fallback: Parser = safe_fallback_parser) -> None:
        self._event_handlers: dict[str, tuple[str, RegexpEventHandler]] = {}
        self._fallback = fallback

    def register_event_handler(self, pattern: str) -> Callable[[RegexpEventHandler], RegexpEventHandler]:
        """Return a decorator that registers a [l2sl.RegexpEventHandler][] for a message pattern.

        The pattern may contain named groups (`(?P<name>...)`); the captured
        values are passed to the handler keyed by the group names.

        Args:
            pattern: Regular expression matched against the log message.

        Returns:
            A decorator that registers the wrapped event handler.
        """

        def decorator(eh: RegexpEventHandler) -> RegexpEventHandler:
            self._event_handlers[_unique_regex_identifier()] = (pattern, eh)
            return eh

        return decorator

    @functools.cached_property
    def _parser(self) -> _RegexpEventParser:
        return _RegexpEventParser(self._event_handlers, self._fallback)

    def __call__(self, record: logging.LogRecord) -> EventDict:
        return self._parser(record)


class _RegexpEventParser:
    def __init__(
        self,
        event_handlers: dict[str, tuple[str, RegexpEventHandler]],
        fallback: Parser,
    ) -> None:
        self._pattern, self._event_map = self._compile(event_handlers)
        self._fallback = fallback

    _GROUP_PATTERN = re.compile(r"\(\?P<(?P<group>\w+)>")

    def _compile(
        self, event_handlers: dict[str, tuple[str, RegexpEventHandler]]
    ) -> tuple[re.Pattern[str], dict[str, tuple[dict[str, str], RegexpEventHandler]]]:
        event_patterns: dict[str, str] = {}
        event_map = {}
        for event_id, (event_pattern, event_handler) in event_handlers.items():
            group_map = {group: _unique_regex_identifier() for group in self._GROUP_PATTERN.findall(event_pattern)}

            event_patterns[event_id] = self._GROUP_PATTERN.sub(
                lambda match: f"(?P<{group_map[match['group']]}>", event_pattern
            )
            event_map[event_id] = (group_map, event_handler)

        pattern = "|".join(f"(?P<{event_id}>{pattern})" for event_id, pattern in event_patterns.items())
        pattern = f"({pattern})"

        return re.compile(pattern), event_map

    def __call__(self, record: logging.LogRecord) -> EventDict:
        event = record.getMessage()
        match = self._pattern.match(event)
        if not match:
            return self._fallback(record)

        groups = match.groupdict()
        group_map, event_handler = next(v for id, v in self._event_map.items() if groups[id] is not None)

        return event_handler({group: groups[group_id] for group, group_id in group_map.items()}, record)


def _unique_regex_identifier() -> str:
    return f"_{secrets.token_hex(8)}"
