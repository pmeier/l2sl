import logging
from collections.abc import Mapping
from typing import Any

from ._parsers import Parser, builtin_parsers


class StdlibRecordParser:
    def __init__(
        self,
        *,
        parsers: dict[str, Parser] | None = None,
        fallback: Parser | None = None,
        include_logger_name: bool | str = True,
    ) -> None:
        if parsers is None:
            parsers = builtin_parsers()
        self._parsers = parsers

        if fallback is None:

            def fallback(
                event: str, record: logging.LogRecord
            ) -> tuple[str, dict[str, Any]]:
                return event, {}

        self._fallback = fallback

        if not isinstance(include_logger_name, str):
            include_logger_name = "logger" if include_logger_name else ""
        self._include_logger_name = include_logger_name

    def __call__(
        self, logger: Any, level: str, event_dict: Mapping[str, Any]
    ) -> dict[str, Any]:
        event_dict = dict(event_dict)
        record: logging.LogRecord | None = event_dict.pop("record", None)
        if record is None:
            return event_dict

        parser = self._parsers.get(record.name, self._fallback)

        event, values = parser(event_dict.pop("event"), record)

        event_dict["event"] = event
        event_dict.update(values)

        if self._include_logger_name:
            event_dict[self._include_logger_name] = record.name

        return event_dict
