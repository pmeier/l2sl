import logging
import sys

import pytest

from l2sl._parse import exc_to_exc_info, safe_fallback_parser


def make_record(
    name: str = "some.lib",
    msg: str = "hello",
    args: tuple | None = None,
    **extra,
) -> logging.LogRecord:
    record = logging.LogRecord(name, logging.INFO, __file__, 1, msg, args, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_clean_record_has_no_error_key():
    event_dict = safe_fallback_parser(make_record())

    assert event_dict["event"] == "hello"
    assert "l2sl_safe_fallback_parser_errors" not in event_dict


def test_level_in_extras_is_renamed_and_flagged():
    event_dict = safe_fallback_parser(make_record(level="sneaky"))

    assert event_dict["extra_level"] == "sneaky"
    assert "level" not in event_dict
    assert event_dict["l2sl_safe_fallback_parser_errors"] == [
        "Reserved key 'level' in record extras. Moved to the 'extra_level' key."
    ]


def test_unformattable_message_is_flagged():
    record = make_record(msg="%s %s", args=("only one arg",))

    event_dict = safe_fallback_parser(record)

    assert event_dict["event"] == "unable to format record message"
    assert event_dict["record_msg"] == "%s %s"
    assert event_dict["record_args"] == ("only one arg",)
    assert event_dict["l2sl_safe_fallback_parser_errors"] == [
        "Unable to format record message. Format message moved to 'record_msg' key "
        "and format arguments to 'record_args' key."
    ]


def test_multiple_errors_accumulate_in_list():
    record = make_record(msg="%s %s", args=("only one arg",), level="sneaky")

    event_dict = safe_fallback_parser(record)

    assert event_dict["l2sl_safe_fallback_parser_errors"] == [
        "Reserved key 'level' in record extras. Moved to the 'extra_level' key.",
        "Unable to format record message. Format message moved to 'record_msg' key "
        "and format arguments to 'record_args' key.",
    ]


def test_unknown_error_is_flagged_and_contains_no_raw_record(monkeypatch):
    def explode(record):
        raise RuntimeError("extraction failed")

    monkeypatch.setattr("l2sl._parse._extract_record_extra", explode)

    event_dict = safe_fallback_parser(make_record())

    assert event_dict["event"] == "unknown event"
    assert event_dict["l2sl_safe_fallback_parser_errors"] == ["Unknown parsing error."]
    assert not any(isinstance(v, logging.LogRecord) for v in event_dict.values())


def test_record_exc_info_is_normalized_to_tuple():
    exc = ValueError("boom")
    try:
        raise exc
    except ValueError:
        record = make_record()
        record.exc_info = exc

    event_dict = safe_fallback_parser(record)

    exc_type, exc_value, tb = event_dict["exc_info"]
    assert exc_type is ValueError
    assert exc_value is exc
    assert tb is not None


def _raise_and_capture(exc):
    try:
        raise exc
    except type(exc):
        return exc, sys.exc_info()


_bare_exc = ValueError("bare")
_raised_exc, _raised_exc_info = _raise_and_capture(ValueError("raised"))


@pytest.mark.parametrize(
    ("exc_info", "expected"),
    [
        pytest.param(_bare_exc, (ValueError, _bare_exc, None), id="bare-instance"),
        pytest.param(_raised_exc, _raised_exc_info, id="raised-instance"),
        pytest.param(_raised_exc_info, _raised_exc_info, id="tuple-passthrough"),
    ],
)
def test_exc_to_exc_info(exc_info, expected):
    assert exc_to_exc_info(exc_info) == expected


@pytest.mark.parametrize("fallback_input", [True, 1, "truthy", None])
def test_exc_to_exc_info_falls_back_to_currently_handled_exception(fallback_input):
    try:
        raise ValueError("ambient")
    except ValueError:
        expected = sys.exc_info()
        assert exc_to_exc_info(fallback_input) == expected
