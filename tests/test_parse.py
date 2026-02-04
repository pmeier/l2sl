import pytest

from l2sl._parse import _LoggerResolver


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
def test_logger_resolver(available_loggers, logger, expected):
    assert expected in available_loggers or expected is None

    logger_resolver = _LoggerResolver(available_loggers)
    assert logger_resolver(logger) == expected
