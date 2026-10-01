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
    """Register a parser as a builtin parser for a logger.

    Can be used directly or as a decorator.

    Args:
        parser: The parser to register. If omitted, a decorator is returned.
        logger: Logger name the parser is registered for, for example
            `"uvicorn.error"`.

    Returns:
        The registered parser, or a decorator that registers one.
    """

    def register(parser: TParser) -> TParser:
        _BUILTIN[logger] = parser
        return parser

    if parser is None:
        return register
    else:
        return register(parser)


def builtin_parsers() -> dict[str, Parser]:
    """Return the parsers bundled with l2sl.

    On the first call, all builtin parser modules are imported so that they
    register themselves.

    Returns:
        A mapping of logger names (for example `"uvicorn.error"`) to parsers.
    """
    if not _BUILTIN:
        for p in sorted(Path(__file__).parent.glob("[!_]*.py")):
            importlib.import_module(f"{__package__}.{p.stem}")
    return _BUILTIN.copy()
