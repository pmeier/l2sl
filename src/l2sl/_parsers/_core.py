__all__ = [
    "Parser",
    "register_builtin_parser",
    "builtin_parsers",
    "load_builtin_parsers",
    "default_fallback_parser",
]

import importlib
import logging
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, TypeVar, overload

Parser = Callable[[str, logging.LogRecord], tuple[str, Mapping[str, Any]]]

_BUILTIN: dict[str, Parser] = {}

P = TypeVar("P", bound=Parser)


@overload
def register_builtin_parser(parser: P, /, *, logger: str) -> P: ...


@overload
def register_builtin_parser(
    parser: None = None, /, *, logger: str
) -> Callable[[P], P]: ...


def register_builtin_parser(
    parser: P | None = None, /, *, logger: str
) -> P | Callable[[P], P]:
    def register(parser: P) -> P:
        _BUILTIN[logger] = parser
        return parser

    if parser is None:
        return register
    else:
        return register(parser)


def load_builtin_parsers() -> None:
    for p in sorted(Path(__file__).parent.glob("[!_]*.py")):
        importlib.import_module(f"{__package__}.{p.stem}")


def builtin_parsers() -> dict[str, Parser]:
    return _BUILTIN.copy()


_DEFAULT_RECORD_ATTRIBUTES = set(
    logging.LogRecord("", logging.DEBUG, "", 0, "", None, None).__dict__.keys()
)


def _extract_record_extra(record: logging.LogRecord) -> dict[str, Any]:
    return {
        k: v for k, v in record.__dict__.items() if k not in _DEFAULT_RECORD_ATTRIBUTES
    }


def default_fallback_parser(
    event: str, record: logging.LogRecord
) -> tuple[str, dict[str, Any]]:
    event_dict: dict[str, Any] = _extract_record_extra(record)
    if exc_info := record.exc_info:
        if isinstance(exc_info, BaseException):
            exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
        elif not isinstance(exc_info, tuple):
            exc_info = sys.exc_info()
        event_dict["exc_info"] = exc_info

    if stack_info := record.stack_info:
        event_dict["stack_info"] = stack_info

    return event, event_dict
