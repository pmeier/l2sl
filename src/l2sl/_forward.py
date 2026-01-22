__all__ = ["configure_stdlib_log_forwarding"]

import logging
import logging.config

import structlog

from ._filter import RecordFilter, SimpleRecordFilter


class _RecordForwarder(logging.Handler):
    def __init__(self, *, record_filter: RecordFilter) -> None:
        super().__init__()
        self._record_filter = record_filter
        self._logger = structlog.get_logger()

    def emit(self, record: logging.LogRecord) -> None:
        if self._record_filter(record):
            self._logger.log(
                record.levelno,
                record.msg,
                *record.args,
                record=record,
            )


def configure_stdlib_log_forwarding(
    *, record_filter: RecordFilter = SimpleRecordFilter.default(level="info")
) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "structlog": {
                    "class": "l2sl._forward._RecordForwarder",
                    "record_filter": record_filter,
                }
            },
            "loggers": {"root": {"level": "NOTSET", "handlers": ["structlog"]}},
        }
    )
