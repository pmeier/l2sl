import logging

import pytest
import structlog

import l2sl
from l2sl._forward import _LoggerResolver, _RecordForwarder


def make_record(name: str = "some.lib", msg: str = "hello") -> logging.LogRecord:
    return logging.LogRecord(name, logging.INFO, __file__, 1, msg, None, None)


def make_handler(mocker, parser=None, **kwargs):
    fake_logger = mocker.Mock()
    handler = _RecordForwarder(
        parsers={"some": parser} if parser is not None else {},
        fallback_parser=kwargs.pop("fallback_parser", l2sl.safe_fallback_parser),
        logger=fake_logger,
        **kwargs,
    )
    return handler, fake_logger


def test_configure_stdlib_log_forwarding_clears_old_handlers():
    foo = logging.getLogger("foo")
    foo_bar = logging.getLogger("foo.bar")

    foo.addHandler(logging.StreamHandler())
    foo_bar.addHandler(logging.StreamHandler())
    logging.root.addHandler(logging.StreamHandler())

    l2sl.configure_stdlib_log_forwarding()

    assert len(logging.root.handlers) == 1
    assert isinstance(logging.root.handlers[0], _RecordForwarder)

    assert foo is logging.getLogger("foo")
    assert len(foo.handlers) == 0
    assert not foo.disabled

    assert foo_bar is logging.getLogger("foo.bar")
    assert len(foo_bar.handlers) == 0
    assert not foo_bar.disabled


def test_configure_stdlib_log_forwarding_enables_propagation():
    foo = logging.getLogger("foo")
    foo_bar = logging.getLogger("foo.bar")
    foo.propagate = False
    foo_bar.propagate = False

    l2sl.configure_stdlib_log_forwarding()

    assert foo.propagate
    assert foo_bar.propagate


def test_configure_stdlib_log_forwarding_unable_to_validate():
    with pytest.raises(RuntimeError, match="not configured"):
        l2sl.configure_stdlib_log_forwarding(validate_structlog_config=True)


def test_configure_stdlib_log_forwarding_not_compatible():
    structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())

    with pytest.raises(RuntimeError, match="not compatible"):
        l2sl.configure_stdlib_log_forwarding()


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
    logger_resolver = _LoggerResolver(available_loggers)
    assert logger_resolver(logger) == expected


def test_parser_exception_uses_safe_fallback_with_correlated_error(mocker):
    def bad_parser(record):
        raise ValueError("parser blew up")

    handler, fake = make_handler(mocker, parser=bad_parser)

    handler.emit(make_record(name="some.lib"))

    fake.error.assert_called_once()
    error_kwargs = fake.error.call_args.kwargs
    assert fake.error.call_args.args == ("using safe fallback parser",)
    assert error_kwargs["reason"] == "failed to parse"
    exc_type, exc_value, _ = error_kwargs["exc_info"]
    assert exc_type is ValueError
    assert isinstance(exc_value, ValueError)

    fake.log.assert_called_once()
    assert fake.log.call_args.kwargs["l2sl_record_id"] == error_kwargs["l2sl_record_id"]
    assert fake.log.call_args.kwargs["logger"] == "some.lib"


def test_non_mapping_return_uses_safe_fallback_with_correlated_error(mocker):
    def bad_parser(record):
        return "not a mapping"

    handler, fake = make_handler(mocker, parser=bad_parser)

    handler.emit(make_record(name="some.lib"))

    fake.error.assert_called_once()
    error_kwargs = fake.error.call_args.kwargs
    assert fake.error.call_args.args == ("using safe fallback parser",)
    assert error_kwargs["reason"] == "parser did not return a mutable mapping"
    assert error_kwargs["returned_type"] == "str"

    fake.log.assert_called_once()
    assert fake.log.call_args.kwargs["l2sl_record_id"] == error_kwargs["l2sl_record_id"]


def test_reserved_level_key_uses_safe_fallback_with_correlated_error(mocker):
    def bad_parser(record):
        return {"event": "parsed", "level": 99}

    handler, fake = make_handler(mocker, parser=bad_parser)

    handler.emit(make_record(name="some.lib"))

    fake.error.assert_called_once()
    error_kwargs = fake.error.call_args.kwargs
    assert fake.error.call_args.args == ("using safe fallback parser",)
    assert error_kwargs["reason"] == "parser returned reserved key 'level'"
    assert error_kwargs["returned_level"] == 99

    fake.log.assert_called_once()
    assert fake.log.call_args.kwargs["l2sl_record_id"] == error_kwargs["l2sl_record_id"]
    # the parsed event is discarded in favor of the safe fallback
    assert fake.log.call_args.args[1] == "hello"


def test_level_in_extra_end_to_end(mocker):
    """``extra={"level": ...}`` is not reserved by stdlib logging and must not break forwarding.

    The safe fallback parser handles the rename itself, so the notification is the
    ``l2sl_safe_fallback_parser_errors`` marker on the logged event rather than a
    separate forwarder error log.
    """
    fake = mocker.Mock()
    l2sl.configure_stdlib_log_forwarding(
        parsers={},
        fallback_parser=l2sl.safe_fallback_parser,
        logger=fake,
        validate_structlog_config=False,
    )

    logging.getLogger("some.lib").info("hello", extra={"level": "sneaky"})

    fake.error.assert_not_called()
    fake.log.assert_called_once()
    assert fake.log.call_args.kwargs["extra_level"] == "sneaky"
    assert "level" not in fake.log.call_args.kwargs
    assert fake.log.call_args.kwargs["l2sl_safe_fallback_parser_errors"] == [
        "Reserved key 'level' in record extras. Moved to the 'extra_level' key."
    ]


def test_drop_event_is_not_logged(mocker):
    def dropping_parser(record):
        raise structlog.exceptions.DropEvent("drop it")

    handler, fake = make_handler(mocker, parser=dropping_parser)

    handler.emit(make_record(name="some.lib"))

    fake.log.assert_not_called()
    fake.error.assert_not_called()


def test_successful_parse_has_no_error_and_no_record_id(mocker):
    def good_parser(record):
        return {"event": "clean", "custom": 1}

    handler, fake = make_handler(mocker, parser=good_parser)

    handler.emit(make_record(name="some.lib"))

    fake.error.assert_not_called()
    fake.log.assert_called_once()
    assert "l2sl_record_id" not in fake.log.call_args.kwargs
