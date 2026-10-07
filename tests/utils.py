import logging
from typing import Any


def make_record(
    name: str = "some.lib",
    msg: str = "hello",
    args: Any = None,
    **extra: Any,
) -> logging.LogRecord:
    record = logging.LogRecord(name, logging.INFO, __file__, 1, msg, args, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record
