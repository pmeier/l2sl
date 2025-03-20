import importlib
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, TypeVar

Parser = Callable[[str, logging.LogRecord], tuple[str, Mapping[str, Any]]]

_BUILTIN: dict[str, Parser] = {}

P = TypeVar("P", bound=Parser)


def register_builtin_parser(logger: str, parser: P) -> P:
    _BUILTIN[logger] = parser
    return parser


def load_builtin_parsers() -> None:
    for p in sorted(Path(__file__).parent.glob("[!_]*.py")):
        importlib.import_module(f"{__package__}.{p.stem}")


def builtin_parsers() -> dict[str, Parser]:
    return _BUILTIN.copy()
