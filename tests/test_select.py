import pytest

from l2sl._select import LoggerSelector


@pytest.mark.parametrize(
    ("available_loggers", "logger", "expected"),
    [
        (["foo", "bar"], "foo", "foo"),
        (["foo", "bar"], "baz", None),
        (["foo.boo", "bar"], "foo", None),
        (["foo.boo", "bar"], "foo.boo", "foo.boo"),
        (["foo", "bar"], "foo.boo", "foo"),
    ],
)
def test_logger_selector(available_loggers, logger, expected):
    logger_selector = LoggerSelector(available_loggers)
    assert logger_selector(logger) == expected
