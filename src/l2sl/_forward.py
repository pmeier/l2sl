__all__ = ["configure_stdlib_log_forwarding"]

import logging
import logging.config
from collections.abc import Mapping

import structlog
from structlog.typing import FilteringBoundLogger

from ._builtin_parsers import builtin_parsers
from ._parse import Parser, ResolvingParser, default_fallback_parser


def configure_stdlib_log_forwarding(
    *,
    parsers: Mapping[str, Parser] | None = None,
    fallback_parser: Parser | None = None,
    logger: FilteringBoundLogger | None = None,
    validate_structlog_config: bool | None = None,
) -> None:
    if parsers is None:
        parsers = builtin_parsers()
    if fallback_parser is None:
        fallback_parser = default_fallback_parser
    if logger is None:
        logger = structlog.get_logger()

    if validate_structlog_config is None:
        validate_structlog_config = structlog.is_configured()
    if validate_structlog_config:
        if not structlog.is_configured():
            raise RuntimeError(
                "unable to validate structlog for usage with l2sl, because it is not configured"
            )

        config = structlog.get_config()
        if isinstance(
            logger_factory := config.get("logger_factory"),
            structlog.stdlib.LoggerFactory,
        ):
            raise RuntimeError(
                f"l2sl is not compatible with structlog's standard library logging, "
                f"but {logger_factory=} is configured"
            )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "l2sl": {
                    "()": _RecordForwarder,
                    "parser": ResolvingParser(
                        parsers=parsers, fallback=fallback_parser, logger=logger
                    ),
                    "logger": logger,
                }
            },
            "loggers": {
                "root": {"level": "NOTSET", "handlers": ["l2sl"]},
            },
        }
    )


class _RecordForwarder(logging.Handler):
    def __init__(self, parser: Parser, logger: FilteringBoundLogger) -> None:
        super().__init__()
        self._parser = parser
        self._logger = logger

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event_dict = self._parser(record)
        except structlog.exceptions.DropEvent:
            return

        self._logger.log(record.levelno, event_dict.pop("event", ""), **event_dict)
