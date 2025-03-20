try:
    from ._version import __version__
except ModuleNotFoundError:
    import warnings

    warnings.warn("l2sl was not properly installed!")
    del warnings

    __version__ = "UNKNOWN"

from ._forward import STDLIB_LOGGERS, configure_stdlib_logging
from ._parsers import Parser, RegexpEventHandler, RegexpEventParser, builtin_parsers
from ._process import StdlibRecordParser

__all__ = ["__version__", "configure_stdlib_logging"]
