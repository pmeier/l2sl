from __future__ import annotations

__all__ = [
    "ResolvingParser",
    "Parser",
    "default_fallback_parser",
    "RegexpEventParser",
    "RegexpEventHandler",
]

import functools
import logging
import re
import secrets
import sys
import uuid
from collections.abc import Iterable, Mapping
from typing import Any, Callable

import structlog
from structlog.typing import EventDict, FilteringBoundLogger

Parser = Callable[[logging.LogRecord], EventDict]

_DEFAULT_RECORD_ATTRIBUTES = set(
    logging.LogRecord("", logging.DEBUG, "", 0, "", None, None).__dict__.keys()
)


def _extract_record_extra(record: logging.LogRecord) -> dict[str, Any]:
    return {
        k: v for k, v in record.__dict__.items() if k not in _DEFAULT_RECORD_ATTRIBUTES
    }


def default_fallback_parser(record: logging.LogRecord) -> EventDict:
    event_dict: dict[str, Any] = _extract_record_extra(record) | {
        "event": record.getMessage()
    }
    if exc_info := record.exc_info:
        if isinstance(exc_info, BaseException):
            exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
        elif not isinstance(exc_info, tuple):
            exc_info = sys.exc_info()
        event_dict["exc_info"] = exc_info

    if stack_info := record.stack_info:
        event_dict["stack_info"] = stack_info

    return event_dict


class ResolvingParser:
    def __init__(
        self,
        *,
        parsers: Mapping[str, Parser],
        fallback: Parser = default_fallback_parser,
        logger: FilteringBoundLogger,
    ) -> None:
        self._parsers = parsers
        self._fallback = fallback
        self._logger = logger

        self._logger_resolver = _LoggerResolver(self._parsers.keys())

    def __call__(self, record: logging.LogRecord) -> EventDict:
        logger = record.name
        resolved_logger = self._logger_resolver(logger)
        parser = (
            self._parsers[resolved_logger]
            if resolved_logger is not None
            else self._fallback
        )

        try:
            event_dict = parser(record)
        except structlog.exceptions.DropEvent:
            raise
        except Exception as exc_info:
            event_dict = self._fallback(record)
            l2sl_parser_error_id = event_dict["l2sl_parser_error_id"] = str(
                uuid.uuid4()
            )
            self._logger.error(
                "failed to parse record",
                logger="l2sl",
                exc_info=exc_info,
                l2sl_parser_error_id=l2sl_parser_error_id,
            )

        event_dict["logger"] = logger
        return event_dict


class _LoggerResolver:
    def __init__(self, available_loggers: Iterable[str]) -> None:
        self._available_loggers = [l.split(".") for l in available_loggers]

    @functools.lru_cache()
    def __call__(self, logger: str) -> str | None:
        l = logger.split(".")
        applicable_loggers = sorted(
            (
                a
                for a in self._available_loggers
                if len(l) >= len(a) and l[: len(a)] == a
            ),
            key=len,
        )
        if not applicable_loggers:
            return None

        return ".".join(applicable_loggers[-1])


RegexpEventHandler = Callable[[dict[str, str], logging.LogRecord], EventDict]


class RegexpEventParser:
    def __init__(self, fallback: Parser = default_fallback_parser) -> None:
        self._event_handlers: dict[str, tuple[str, RegexpEventHandler]] = {}
        self._fallback = fallback

    def register_event_handler(
        self, pattern: str
    ) -> Callable[[RegexpEventHandler], RegexpEventHandler]:
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
            group_map = {
                group: _unique_regex_identifier()
                for group in self._GROUP_PATTERN.findall(event_pattern)
            }

            event_patterns[event_id] = self._GROUP_PATTERN.sub(
                lambda match: f"(?P<{group_map[match['group']]}>", event_pattern
            )
            event_map[event_id] = (group_map, event_handler)

        pattern = "|".join(
            f"(?P<{event_id}>{pattern})" for event_id, pattern in event_patterns.items()
        )
        pattern = f"({pattern})"

        return re.compile(pattern), event_map

    def __call__(self, record: logging.LogRecord) -> EventDict:
        event = record.getMessage()
        match = self._pattern.match(event)
        if not match:
            return self._fallback(record)

        groups = match.groupdict()
        group_map, event_handler = next(
            v for id, v in self._event_map.items() if groups[id] is not None
        )

        return event_handler(
            {group: groups[group_id] for group, group_id in group_map.items()}, record
        )


def _unique_regex_identifier() -> str:
    return f"_{secrets.token_hex(8)}"
