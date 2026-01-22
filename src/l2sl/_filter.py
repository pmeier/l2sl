from __future__ import annotations

__all__ = [
    "RecordFilter",
    "SimpleRecordFilter",
    "StdlibLogLevel",
    "StdlibLogLevelNumber",
    "StructlogLogLevel",
    "LogLevel",
]

import logging
import sys
from collections import defaultdict
from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING, Callable, Literal

from ._select import LoggerSelector

if TYPE_CHECKING:
    if sys.version_info < (3, 11):
        from typing_extensions import Self
    else:
        from typing import Self


RecordFilter = Callable[[logging.LogRecord], bool]

StdlibLogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]
StdlibLogLevelNumber = Literal[50, 40, 30, 20, 10, 0]
StructlogLogLevel = Literal[
    "critical", "error", "warning", "warn", "info", "debug", "notset"
]

LogLevel = StdlibLogLevel | StdlibLogLevelNumber | StructlogLogLevel

_LOG_LEVEL_NUMBERS = {50, 40, 30, 20, 10, 0}
_LOG_LEVEL_MAP = {
    "critical": 50,
    "error": 40,
    "warning": 30,
    "warn": 30,
    "info": 20,
    "debug": 10,
    "notset": 0,
}


_Mode = Literal["include", "exclude"]


class SimpleRecordFilter:
    @classmethod
    def default(cls, *, level: LogLevel = "info") -> Self:
        stdlib_loggers = ["asyncio", "concurrent"]
        return cls.exclude(stdlib_loggers, default_level=level)

    @classmethod
    def include(
        cls,
        loggers: Mapping[str, LogLevel] | Collection[str],
        *,
        default_level: LogLevel = "info",
    ) -> Self:
        return cls._new(loggers=loggers, default_level=default_level, mode="include")

    @classmethod
    def exclude(
        cls,
        loggers: Mapping[str, LogLevel] | Collection[str],
        *,
        default_level: LogLevel = "info",
    ) -> Self:
        return cls._new(loggers=loggers, default_level=default_level, mode="exclude")

    @classmethod
    def _new(
        cls,
        *,
        loggers: Mapping[str, LogLevel] | Collection[str],
        default_level: LogLevel,
        mode: _Mode,
    ) -> Self:
        default_level_number = cls._log_level_to_number(default_level)
        if isinstance(loggers, Mapping):
            levels = {
                logger: cls._log_level_to_number(level)
                for logger, level in loggers.items()
            }
        else:
            levels = {logger: default_level_number for logger in loggers}
        return cls(levels=defaultdict(lambda: default_level_number, levels), mode=mode)

    @staticmethod
    def _log_level_to_number(level: LogLevel) -> int:
        def invalid() -> Exception:
            names = ",".join(f"'{n}'" for n in _LOG_LEVEL_MAP.keys())
            numbers = ",".join(
                [str(n) for n in sorted(_LOG_LEVEL_NUMBERS, reverse=True)]
            )
            return ValueError(
                f"level can be case-insensitive string ({names}) or as corresponding integer ({numbers}), "
                f"but got {level}"
            )

        if isinstance(level, int):
            if level not in _LOG_LEVEL_NUMBERS:
                raise invalid()

            return level

        try:
            return _LOG_LEVEL_MAP[level.lower()]
        except KeyError:
            raise invalid() from None

    def __init__(self, *, levels: defaultdict[str | None, int], mode: _Mode) -> None:
        self._levels = levels
        self._mode = mode
        self._logger_selector = LoggerSelector(levels.keys())

    def __call__(self, record: logging.LogRecord) -> bool:
        logger = self._logger_selector(record.name)
        match self._mode:
            case "include":
                return logger is not None and self._levels[logger] <= record.levelno
            case "exclude":
                return logger is None

        # what if exclude is foo.bar
        # and we have a level value for foo

        if (self._mode == "include" and logger is None) or (
            self._mode == "exclude" and logger is not None
        ):
            return False

        return
