from __future__ import annotations

__all__ = [
    "Parser",
    "ParserArgsError",
    "RegexpEventParser",
    "RegexpEventHandler",
    "exc_to_exc_info",
    "expect_tuple_args",
    "safe_fallback_parser",
]

import logging
import re
import secrets
import sys
import warnings
from collections.abc import Mapping
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


class ParserArgsError(ValueError):
    """A record's format arguments do not match the shape a parser expects.

    Raised by [l2sl.expect_tuple_args][] when `record.args` cannot be unpacked as expected. The forwarding machinery
    catches this and reports the message as the reason for falling back, so a mismatched record degrades to the fallback
    parser instead of getting lost behind a bare unpacking failure.

    Args:
        record: The record whose format arguments did not match.
        message: Human-readable description of the mismatch.

    Attributes:
        record: The [logging.LogRecord][] that triggered the error.
    """

    def __init__(self, record: logging.LogRecord, message: str) -> None:
        super().__init__(message)
        self.record = record


def expect_tuple_args(record: logging.LogRecord, expected: int) -> tuple[Any, ...]:
    """Return `record.args` as a tuple of `expected` positional format arguments.

    `record.args` is normalized only in so far as a record logged without arguments is treated as an empty
    tuple. A record that carries its arguments as a mapping (the `logger.info("%(name)s", {...})` style, which
    [logging][] unwraps out of the argument tuple) is never converted: it has no positional shape and is
    reported as a mismatch.

    Args:
        record: The stdlib [logging.LogRecord][] whose format arguments to check.
        expected: The number of positional format arguments the caller unpacks.

    Returns:
        The record's format arguments, guaranteed to hold exactly `expected` items.

    Raises:
        ParserArgsError: If the record uses dict-style (`%(name)s`) formatting, if its arguments are neither a
            tuple nor absent, or if the number of arguments differs from `expected`.
    """
    args: Any = () if record.args is None else record.args
    expected_args = f"Expected {expected} positional format argument(s) for logger {record.name!r}"

    if isinstance(args, Mapping):
        raise ParserArgsError(
            record,
            f"{expected_args}, but the record uses dict-style (%(name)s) formatting with keys {sorted(args)!r}",
        )

    if not isinstance(args, tuple):
        raise ParserArgsError(record, f"{expected_args}, but its format arguments are of type {type(args).__name__}")

    if len(args) != expected:
        raise ParserArgsError(record, f"{expected_args}, got {len(args)}: {args!r}")

    return args


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
        self._parser: _RegexpEventParser | None = None
        self._fallback = fallback

    def register_event_handler(self, pattern: str) -> Callable[[RegexpEventHandler], RegexpEventHandler]:
        """Return a decorator that registers a [l2sl.RegexpEventHandler][] for a message pattern.

        The pattern may contain named groups (`(?P<name>...)`); the captured
        values are passed to the handler keyed by the group names.

        Args:
            pattern: Regular expression matched against the log message.

        Returns:
            A decorator that registers the wrapped event handler.

        Raises:
            RuntimeError: If the patterns were already compiled into the combined regexp, i.e. if records have
                already been parsed. Registering late would silently have no effect, so this fails loudly.
        """

        def decorator(eh: RegexpEventHandler) -> RegexpEventHandler:
            if self._parser is not None:
                raise RuntimeError(
                    "Cannot register an event handler after the parser has been compiled. All event handlers must be "
                    "registered before the first record is parsed."
                )
            self._event_handlers[_unique_regex_identifier()] = (pattern, eh)
            return eh

        return decorator

    def __call__(self, record: logging.LogRecord) -> EventDict:
        if self._parser is None:
            self._parser = _RegexpEventParser(self._event_handlers, self._fallback)
        return self._parser(record)


class _RegexpEventParser:
    def __init__(
        self,
        event_handlers: dict[str, tuple[str, RegexpEventHandler]],
        fallback: Parser,
    ) -> None:
        self._pattern: re.Pattern[str] | None
        if event_handlers:
            self._pattern, self._event_map = self._compile(event_handlers)
        else:
            # Without handlers the combined regexp would compile to "()", which matches the empty prefix of every
            # message and leaves the handler lookup without a match. Warn instead, since this is almost certainly
            # not what the user wanted, and route everything to the fallback.
            warnings.warn(
                "RegexpEventParser has no registered event handlers: all records are routed to the fallback parser.",
                stacklevel=3,  # _RegexpEventParser.__init__ -> RegexpEventParser.__call__ -> user code
            )
            self._pattern, self._event_map = None, {}

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
        if self._pattern is None:
            return self._fallback(record)

        event = record.getMessage()
        match = self._pattern.match(event)
        if not match:
            return self._fallback(record)

        groups = match.groupdict()
        group_map, event_handler = next(v for id, v in self._event_map.items() if groups[id] is not None)

        return event_handler({group: groups[group_id] for group, group_id in group_map.items()}, record)


def _unique_regex_identifier() -> str:
    return f"_{secrets.token_hex(8)}"
