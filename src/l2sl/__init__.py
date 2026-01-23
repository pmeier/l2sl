try:
    from ._version import __version__
except ModuleNotFoundError:
    import warnings

    warnings.warn("l2sl was not properly installed!")
    del warnings

    __version__ = "UNKNOWN"

from ._forward import configure_stdlib_log_forwarding
from ._log_level import (
    LogLevel,
    LogLevelNumber,
    StdlibLogLevelName,
    StructlogLogLevelName,
)
from ._parsers import (
    Parser,
    RegexpEventHandler,
    RegexpEventParser,
    builtin_parsers,
    default_fallback_parser,
)
from ._process import StdlibRecordParser

__all__ = [
    "LogLevel",
    "LogLevelNumber",
    "StdlibLogLevelName",
    "StructlogLogLevelName",
    "__version__",
    "configure_stdlib_log_forwarding",
    "Parser",
    "builtin_parsers",
    "default_fallback_parser",
    "RegexpEventHandler",
    "RegexpEventParser",
    "StdlibRecordParser",
]
