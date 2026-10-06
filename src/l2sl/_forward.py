__all__ = ["configure_stdlib_log_forwarding"]

import logging
import logging.config
import uuid
from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any

import structlog
from structlog.typing import EventDict, FilteringBoundLogger

from ._builtin_parsers import builtin_parsers
from ._parse import Parser, exc_to_exc_info, safe_fallback_parser


def configure_stdlib_log_forwarding(
    *,
    parsers: Mapping[str, Parser] | None = None,
    fallback_parser: Parser | None = None,
    logger: FilteringBoundLogger | None = None,
    validate_structlog_config: bool | None = None,
) -> None:
    """Configure stdlib [logging][] to forward all records into a [structlog][] pipeline.

    Installs a forwarding handler on the root logger and clears all existing handlers, so records emitted by any
    library are parsed into structured events and logged through `logger`.

    Args:
        parsers: Mapping of logger names (for example `"uvicorn.error"`) to the parser used for that logger and its
            children. Defaults to [l2sl.builtin_parsers][].
        fallback_parser: Parser used for records whose logger does not match any entry in `parsers`. Defaults to
            [l2sl.safe_fallback_parser][].
        logger: Structlog logger the parsed events are logged with. Defaults to [structlog.get_logger][].
        validate_structlog_config: If `True`, check that structlog is configured in a way that is compatible with l2sl.
            If `None` (default), the check runs whenever [structlog][] is already configured.

    Raises:
        RuntimeError: If validation is enabled and [structlog][] is not configured, or is configured with
            [structlog.stdlib.LoggerFactory][], which is incompatible with l2sl.
    """
    if parsers is None:
        parsers = builtin_parsers()
    if fallback_parser is None:
        fallback_parser = safe_fallback_parser
    if logger is None:
        logger = structlog.get_logger()

    if validate_structlog_config is None:
        validate_structlog_config = structlog.is_configured()
    if validate_structlog_config:
        if not structlog.is_configured():
            raise RuntimeError("unable to validate structlog for usage with l2sl, because it is not configured")

        config = structlog.get_config()
        if isinstance(
            logger_factory := config.get("logger_factory"),
            structlog.stdlib.LoggerFactory,
        ):
            raise RuntimeError(
                f"l2sl is not compatible with structlog's standard library logging, but {logger_factory=} is configured"
            )

    # Clear all existing handlers so nothing leaks from a previous config. logging.config.dictConfig only clears root's
    # handlers; non-root loggers keep theirs unless they're explicitly listed in the new config.
    # disable_existing_loggers cannot be used as it also clears the loggers and not just the handlers.
    for obj in logging.root.manager.loggerDict.values():
        if isinstance(obj, logging.Logger):
            obj.handlers.clear()
            obj.propagate = True
    logging.root.handlers.clear()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "l2sl": {
                    "()": _RecordForwarder,
                    "parsers": parsers,
                    "fallback_parser": fallback_parser,
                    "logger": logger,
                }
            },
            "loggers": {
                "root": {"level": "NOTSET", "handlers": ["l2sl"]},
            },
        }
    )


class _RecordForwarder(logging.Handler):
    def __init__(
        self,
        parsers: Mapping[str, Parser],
        fallback_parser: Parser,
        logger: FilteringBoundLogger,
    ) -> None:
        super().__init__()
        self._parsers = parsers
        self._fallback_parser = fallback_parser
        self._logger = logger

        self._logger_resolver = _LoggerResolver(self._parsers.keys())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event_dict = self._parse(record)
        except structlog.exceptions.DropEvent:
            return

        self._logger.log(record.levelno, event_dict.pop("event", ""), **event_dict)

    def _parse(self, record: logging.LogRecord) -> EventDict:
        logger = record.name
        resolved_logger = self._logger_resolver(logger)
        parser = self._parsers[resolved_logger] if resolved_logger is not None else self._fallback_parser

        try:
            event_dict = parser(record)
        except structlog.exceptions.DropEvent:
            raise
        except Exception as exc:
            event_dict = self._safe_fallback_event_dict(record, reason="failed to parse", exc_info=exc_to_exc_info(exc))

        if not isinstance(event_dict, MutableMapping):
            event_dict = self._safe_fallback_event_dict(
                record,
                reason="parser did not return a mutable mapping",
                returned_type=type(event_dict).__name__,
            )

        # "level" is a reserved key when the event_dict gets logged and cannot be overridden
        if "level" in event_dict:
            event_dict = self._safe_fallback_event_dict(
                record,
                reason="parser returned reserved key 'level'",
                returned_level=event_dict["level"],
            )

        event_dict["logger"] = logger
        return event_dict

    def _safe_fallback_event_dict(self, record: logging.LogRecord, *, reason: str, **kwargs: Any) -> EventDict:
        l2sl_record_id = str(uuid.uuid4())
        self._logger.error(
            "using safe fallback parser",
            logger="l2sl",
            l2sl_record_id=l2sl_record_id,
            reason=reason,
            **kwargs,
        )

        event_dict = safe_fallback_parser(record)
        event_dict["l2sl_record_id"] = l2sl_record_id
        return event_dict


class _LoggerResolver:
    def __init__(self, available_loggers: Iterable[str]) -> None:
        self._available_loggers = [l.split(".") for l in available_loggers]
        self._cache: dict[str, str | None] = {}

    def __call__(self, logger: str) -> str | None:
        if logger in self._cache:
            return self._cache[logger]

        resolved = self._resolve(logger)
        self._cache[logger] = resolved
        return resolved

    def _resolve(self, logger: str) -> str | None:
        ls = logger.split(".")
        applicable_loggers = sorted(
            (l for l in self._available_loggers if len(ls) >= len(l) and ls[: len(l)] == l),
            key=len,
        )
        if not applicable_loggers:
            return None

        return ".".join(applicable_loggers[-1])
