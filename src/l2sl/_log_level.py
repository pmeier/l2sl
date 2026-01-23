from __future__ import annotations

__all__ = ["LogLevel", "LogLevelNumber", "StructlogLogLevelName", "StdlibLogLevelName"]

import functools
from typing import Any, ClassVar, Literal, cast

try:
    import pydantic
    from pydantic_core import core_schema

    _PYDANTIC_2_AVAILABLE = tuple(map(int, pydantic.__version__.split(".")[:3])) >= (2,)
except (ImportError, AttributeError):
    _PYDANTIC_2_AVAILABLE = False

LogLevelNumber = Literal[0, 10, 20, 30, 40, 50]
StdlibLogLevelName = Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
StructlogLogLevelName = Literal[
    "notset", "debug", "info", "warning", "warn", "error", "exception", "critical"
]


@functools.total_ordering
class LogLevel:
    _NUMBER_TO_STDLIB_NAME: ClassVar[dict[LogLevelNumber, StdlibLogLevelName]] = {
        0: "NOTSET",
        10: "DEBUG",
        20: "INFO",
        30: "WARNING",
        40: "ERROR",
        50: "CRITICAL",
    }
    _STRUCTLOG_NAME_TO_STDLIB_NAME: dict[StructlogLogLevelName, StdlibLogLevelName] = {
        "notset": "NOTSET",
        "debug": "DEBUG",
        "info": "INFO",
        "warning": "WARNING",
        "warn": "WARNING",
        "error": "ERROR",
        "exception": "ERROR",
        "critical": "CRITICAL",
    }
    _STDLIB_NAME_TO_NUMBER: ClassVar[dict[StdlibLogLevelName, LogLevelNumber]] = {
        v: k for k, v in _NUMBER_TO_STDLIB_NAME.items()
    }
    _STDLIB_NAME_TO_STRUCTLOG_NAME: dict[StdlibLogLevelName, StructlogLogLevelName] = {
        "NOTSET": "notset",
        "DEBUG": "debug",
        "INFO": "info",
        "WARNING": "warning",
        "ERROR": "error",
        "CRITICAL": "critical",
    }

    def __init__(
        self, level: LogLevelNumber | StdlibLogLevelName | StructlogLogLevelName
    ) -> None:
        if (number := cast(LogLevelNumber, level)) in self._NUMBER_TO_STDLIB_NAME:
            stdlib_name = self._NUMBER_TO_STDLIB_NAME[number]
            structlog_name = self._STDLIB_NAME_TO_STRUCTLOG_NAME[stdlib_name]
        elif (
            stdlib_name := cast(StdlibLogLevelName, level)
        ) in self._STDLIB_NAME_TO_NUMBER:
            number = self._STDLIB_NAME_TO_NUMBER[stdlib_name]
            structlog_name = self._STDLIB_NAME_TO_STRUCTLOG_NAME[stdlib_name]
        elif (
            structlog_name := cast(StructlogLogLevelName, level)
        ) in self._STRUCTLOG_NAME_TO_STDLIB_NAME:
            stdlib_name = self._STRUCTLOG_NAME_TO_STDLIB_NAME[structlog_name]
            number = self._STDLIB_NAME_TO_NUMBER[stdlib_name]
        else:
            raise ValueError

        self._number = number
        self._stdlib_name = stdlib_name
        self._structlog_name = structlog_name

    @property
    def number(self) -> LogLevelNumber:
        return self._number

    @property
    def stdlib_name(self) -> StdlibLogLevelName:
        return self._stdlib_name

    @property
    def structlog_name(self) -> StructlogLogLevelName:
        return self._structlog_name

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LogLevel):
            try:
                other = LogLevel(other)
            except ValueError:
                return NotImplemented
        other: LogLevel

        return self.number == other.number

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, LogLevel):
            try:
                other = LogLevel(other)
            except ValueError:
                return NotImplemented
        other: LogLevel

        return self.number < other.number

    def __str__(self) -> str:
        return self.stdlib_name

    def __repr__(self) -> str:
        return f"{type(self)}(number={self.number}, stdlib_name={self.stdlib_name}, structlog_name={self.structlog_name})"

    def __int__(self) -> int:
        return self.number

    if _PYDANTIC_2_AVAILABLE:

        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: Any, _handler: pydantic.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            json_schema = core_schema.chain_schema(
                [
                    core_schema.literal_schema(
                        [
                            *cls._NUMBER_TO_STDLIB_NAME,
                            *cls._STDLIB_NAME_TO_NUMBER,
                            *cls._STRUCTLOG_NAME_TO_STDLIB_NAME,
                        ]
                    ),
                    core_schema.no_info_plain_validator_function(cls),
                ]
            )

            return core_schema.json_or_python_schema(
                json_schema=json_schema,
                python_schema=core_schema.union_schema(
                    [
                        core_schema.is_instance_schema(cls),
                        json_schema,
                    ]
                ),
                serialization=core_schema.plain_serializer_function_ser_schema(str),
            )
