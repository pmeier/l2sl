__all__ = ["configure_stdlib_log_forwarding"]

import logging
import logging.config

import structlog


class _RecordForwarder(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self._logger = structlog.get_logger()

    def emit(self, record: logging.LogRecord) -> None:
        self._logger.log(
            record.levelno,
            record.msg,
            *record.args,
            record=record,
        )


def configure_stdlib_log_forwarding() -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "structlog": {
                    "class": "l2sl._forward._RecordForwarder",
                }
            },
            "loggers": {"root": {"level": "NOTSET", "handlers": ["structlog"]}},
        }
    )
