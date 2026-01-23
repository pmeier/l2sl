__all__ = ["StdlibRecordParser"]

import logging
import uuid
from collections.abc import Mapping
from typing import Any, cast

import structlog

from ._parsers import Parser, builtin_parsers, default_fallback_parser
from ._select import LoggerSelector


class StdlibRecordParser:
    def __init__(
        self,
        *,
        parsers: dict[str, Parser] | None = None,
        fallback: Parser = default_fallback_parser,
    ) -> None:
        if parsers is None:
            parsers = builtin_parsers()
        self._parsers = parsers

        self._fallback = fallback
        self._logger_selector = LoggerSelector(self._parsers.keys())

        self._logger = structlog.get_logger()

    def __call__(
        self, logger: Any, level: str, event_dict: Mapping[str, Any]
    ) -> dict[str, Any]:
        event_dict = dict(event_dict)
        record: logging.LogRecord | None = event_dict.pop("record", None)
        if record is None:
            return event_dict

        logger = record.name
        event_dict["logger"] = logger

        selected_logger = self._logger_selector(logger)
        parser = (
            self._parsers[selected_logger]
            if selected_logger is not None
            else self._fallback
        )

        event = event_dict.pop("event")
        try:
            event, values = parser(event, record)
        except Exception as exc_info:
            event, values = self._fallback(event, record)
            l2sl_error_id = cast(dict[str, Any], values)["l2sl_error_id"] = str(
                uuid.uuid4()
            )
            self._logger.error(
                "failed to parse event",
                logger="l2sl",
                exc_info=exc_info,
                l2sl_error_id=l2sl_error_id,
            )

        event_dict["event"] = event
        event_dict.update(values)

        return event_dict
