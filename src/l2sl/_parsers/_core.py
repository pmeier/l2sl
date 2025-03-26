import importlib
import logging
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
