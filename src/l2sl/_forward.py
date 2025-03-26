import logging
import logging.config
from collections.abc import Collection

import structlog

from ._utils import LoggerSelector


class RecordForwarder(logging.Handler):
    def __init__(self, *, forward: Collection[str]) -> None:
        super().__init__()
        self._logger_selector = LoggerSelector(forward)
        self._logger = structlog.get_logger()

    def emit(self, record: logging.LogRecord) -> None:
        if self._logger_selector(record.name):
            self._logger.log(
                record.levelno,
                record.msg,
                *record.args,
                record=record,
            )


STDLIB_LOGGERS = ["asyncio", "concurrent"]


def configure_stdlib_logging(
    *, include: Collection[str] | None = None, exclude: Collection[str] | None = None
) -> list[str]:
    if include is not None and exclude is not None:
        raise ValueError("included and excluded cannot be passed at the same time")

    available = set(logging.root.manager.loggerDict.keys())
    for name in available:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.filters.clear()
        logger.propagate = True

    if include is not None:
        forward = include
    else:
        if exclude is None:
            exclude = STDLIB_LOGGERS
        forward = available - set(exclude)
    forward = sorted(forward)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "structlog": {
                    "class": "l2sl._forward.RecordForwarder",
                    "forward": forward,
                }
            },
            "loggers": {"root": {"level": "NOTSET", "handlers": ["structlog"]}},
        }
    )

    return forward
