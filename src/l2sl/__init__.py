"""l2sl: forward stdlib [logging][] records into a [structlog][] pipeline."""

try:
    from ._version import __version__
except ModuleNotFoundError:
    import warnings

    warnings.warn("l2sl was not properly installed!")
    del warnings

    __version__ = "UNKNOWN"

from ._builtin_parsers import builtin_parsers
from ._forward import configure_stdlib_log_forwarding
from ._log_level import (
    LogLevel,
    LogLevelNumber,
    StdlibLogLevelName,
    StructlogLogLevelName,
)
from ._parse import Parser, RegexpEventHandler, RegexpEventParser, safe_fallback_parser

__all__ = [
    "LogLevel",
    "LogLevelNumber",
    "StdlibLogLevelName",
    "StructlogLogLevelName",
    "__version__",
    "configure_stdlib_log_forwarding",
    "Parser",
    "builtin_parsers",
    "safe_fallback_parser",
    "RegexpEventHandler",
    "RegexpEventParser",
]
