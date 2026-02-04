__all__ = ["builtin_parsers", "register_builtin_parser"]

import importlib
from pathlib import Path
from typing import Callable, TypeVar, overload

from .._parse import Parser

_BUILTIN: dict[str, Parser] = {}

TParser = TypeVar("TParser", bound=Parser)


@overload
def register_builtin_parser(parser: TParser, /, *, logger: str) -> TParser: ...


@overload
def register_builtin_parser(
    parser: None = None, /, *, logger: str
) -> Callable[[TParser], TParser]: ...


def register_builtin_parser(
    parser: TParser | None = None, /, *, logger: str
) -> TParser | Callable[[TParser], TParser]:
    def register(parser: TParser) -> TParser:
        _BUILTIN[logger] = parser
        return parser

    if parser is None:
        return register
    else:
        return register(parser)


def builtin_parsers() -> dict[str, Parser]:
    if not _BUILTIN:
        for p in sorted(Path(__file__).parent.glob("[!_]*.py")):
            importlib.import_module(f"{__package__}.{p.stem}")
    return _BUILTIN.copy()
