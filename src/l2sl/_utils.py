import functools
import logging
import sys
from collections.abc import Collection
from typing import Any


class LoggerSelector:
    def __init__(self, available_loggers: Collection[str]) -> None:
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


_DEFAULT_RECORD_ATTRIBUTES = set(
    logging.LogRecord("", logging.DEBUG, "", 0, "", None, None).__dict__.keys()
)
# protect the internal one from being modified
DEFAULT_RECORD_ATTRIBUTES = _DEFAULT_RECORD_ATTRIBUTES.copy()


def extract_record_extra(record: logging.LogRecord) -> dict[str, Any]:
    return {
        k: v for k, v in record.__dict__.items() if k not in _DEFAULT_RECORD_ATTRIBUTES
    }


def default_fallback_parser(
    event: str, record: logging.LogRecord
) -> tuple[str, dict[str, Any]]:
    event_dict: dict[str, Any] = extract_record_extra(record)
    if exc_info := record.exc_info:
        if isinstance(exc_info, BaseException):
            exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
        elif not isinstance(exc_info, tuple):
            exc_info = sys.exc_info()
        event_dict["exc_info"] = exc_info

    if stack_info := record.stack_info:
        event_dict["stack_info"] = stack_info

    return event, event_dict
