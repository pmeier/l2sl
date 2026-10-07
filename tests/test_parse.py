import logging
import re
import sys

import pytest
from structlog.exceptions import DropEvent

from l2sl._builtin_parsers.uvicorn import uvicorn_access
from l2sl._forward import _RecordForwarder
from l2sl._parse import (
    ParserArgsError,
    RegexpEventParser,
    exc_to_exc_info,
    expect_tuple_args,
    safe_fallback_parser,
)
from tests.utils import make_record


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


def test_expect_tuple_args_returns_the_tuple_of_expected_length():
    assert expect_tuple_args(make_record(args=("a", "b")), 2) == ("a", "b")


def test_expect_tuple_args_treats_absent_args_as_an_empty_tuple():
    assert expect_tuple_args(make_record(args=None), 0) == ()


def test_expect_tuple_args_reports_logger_and_counts_for_too_few_args():
    with pytest.raises(
        ParserArgsError,
        match=r"Expected 3 positional format argument\(s\) for logger 'some\.lib', got 1: \('a',\)",
    ):
        expect_tuple_args(make_record(args=("a",)), 3)


def test_expect_tuple_args_reports_logger_and_counts_for_too_many_args():
    with pytest.raises(
        ParserArgsError, match=r"Expected 1 positional format argument\(s\) for logger 'some\.lib', got 2"
    ):
        expect_tuple_args(make_record(args=("a", "b")), 1)


def test_expect_tuple_args_reports_dict_style_args_as_such():
    record = make_record(msg="%(a)s %(b)s", args={"a": 1, "b": 2})
    with pytest.raises(ParserArgsError, match=r"dict-style \(%\(name\)s\) formatting with keys \['a', 'b'\]"):
        expect_tuple_args(record, 2)


def test_expect_tuple_args_reports_the_type_of_non_tuple_args():
    with pytest.raises(ParserArgsError, match=r"format arguments are of type str"):
        expect_tuple_args(make_record(args="solo"), 1)


def test_parser_args_error_carries_the_offending_record():
    record = make_record(name="some.lib", args=("a",))
    with pytest.raises(ParserArgsError) as excinfo:
        expect_tuple_args(record, 2)
    assert excinfo.value.record is record


def make_forwarder(mocker, fallback_parser):
    fake = mocker.Mock()
    return _RecordForwarder(parsers={}, fallback_parser=fallback_parser, logger=fake), fake


def test_builtin_parser_mismatch_reason_reaches_safe_fallback(mocker):
    handler, fake = make_forwarder(mocker, uvicorn_access)

    handler.emit(make_record(name="uvicorn.access", msg="request %s", args=("GET",)))

    assert fake.error.call_args.args == ("using safe fallback parser",)
    error_kwargs = fake.error.call_args.kwargs
    expected_reason = "Expected 5 positional format argument(s) for logger 'uvicorn.access', got 1: ('GET',)"
    assert error_kwargs["reason"] == expected_reason
    assert isinstance(error_kwargs["exc_info"][1], ParserArgsError)

    assert fake.log.call_args.args[1] == "request GET"
    assert fake.log.call_args.kwargs["l2sl_record_id"] == error_kwargs["l2sl_record_id"]
    assert fake.log.call_args.kwargs["logger"] == "uvicorn.access"


def test_builtin_parser_dict_style_mismatch_reaches_safe_fallback(mocker):
    handler, fake = make_forwarder(mocker, uvicorn_access)

    handler.emit(make_record(name="uvicorn.access", msg="%(m)s %(p)s", args={"m": "GET", "p": "/"}))

    reason = fake.error.call_args.kwargs["reason"]
    assert reason.endswith("dict-style (%(name)s) formatting with keys ['m', 'p']")
    assert fake.log.call_args.args[1] == "GET /"


def test_builtin_parser_with_matching_args_does_not_use_fallback(mocker):
    handler, fake = make_forwarder(mocker, uvicorn_access)

    handler.emit(make_record(name="uvicorn.access", args=("127.0.0.1", "GET", "/index", "1.1", 200)))

    fake.error.assert_not_called()
    assert fake.log.call_args.kwargs["status_code"] == 200
    assert fake.log.call_args.kwargs["protocol"] == "HTTP/1.1"


def test_matching_message_returns_handler_result():
    parser = RegexpEventParser()

    @parser.register_event_handler(r"hello")
    def handler(groups, record):
        return {"event": "greeting", "level": "info"}

    assert parser(make_record(msg="hello")) == {"event": "greeting", "level": "info"}


def test_named_groups_are_passed_keyed_by_group_name():
    parser = RegexpEventParser()
    captured = {}

    @parser.register_event_handler(r"(?P<who>\w+) ate (?P<what>\d+) (?P<unit>\w+)")
    def handler(groups, record):
        captured.update(groups)
        return {"event": "ate"}

    parser(make_record(msg="phil ate 3 apples"))

    assert captured == {"who": "phil", "what": "3", "unit": "apples"}


def test_handler_receives_the_original_record():
    parser = RegexpEventParser()
    record = make_record(msg="ping", extra_key="carried through")
    seen = {}

    @parser.register_event_handler(r"ping")
    def handler(groups, received):
        seen["record"] = received
        return {"event": "pong"}

    parser(record)

    assert seen["record"] is record
    assert seen["record"].extra_key == "carried through"


def test_pattern_without_named_groups_gets_empty_dict():
    parser = RegexpEventParser()
    calls = []

    @parser.register_event_handler(r"no groups here")
    def handler(groups, record):
        calls.append(groups)
        return {"event": "ok"}

    parser(make_record(msg="no groups here"))

    assert calls == [{}]


def test_non_matching_message_goes_to_custom_fallback():
    calls = []

    def fallback(record):
        calls.append(record)
        return {"event": "fell back"}

    parser = RegexpEventParser(fallback=fallback)

    @parser.register_event_handler(r"never matches")
    def handler(groups, record):
        return {"event": "handled"}

    record = make_record(msg="something else")

    assert parser(record) == {"event": "fell back"}
    assert calls == [record]


def test_default_fallback_is_safe_fallback_parser():
    parser = RegexpEventParser()

    @parser.register_event_handler(r"handled")
    def handler(groups, record):
        return {"event": "handled"}

    assert parser(make_record(msg="unhandled message")) == {"event": "unhandled message"}


def test_patterns_match_at_the_start_of_the_message_only():
    parser = RegexpEventParser()

    @parser.register_event_handler(r"bar")
    def handler(groups, record):
        return {"event": "handled"}

    # re.match, not re.search: "bar" mid-message must not route to the handler
    assert parser(make_record(msg="foo bar"))["event"] == "foo bar"


def test_multiple_handlers_route_per_message():
    parser = RegexpEventParser()

    @parser.register_event_handler(r"alpha (?P<n>\d+)")
    def alpha(groups, record):
        return {"event": "alpha", "n": groups["n"]}

    @parser.register_event_handler(r"beta (?P<n>\d+)")
    def beta(groups, record):
        return {"event": "beta", "n": groups["n"]}

    assert parser(make_record(msg="alpha 1")) == {"event": "alpha", "n": "1"}
    assert parser(make_record(msg="beta 2")) == {"event": "beta", "n": "2"}


def test_duplicate_group_names_across_patterns_do_not_collide():
    parser = RegexpEventParser()

    @parser.register_event_handler(r"A (?P<thing>\d+)")
    def a(groups, record):
        return {"event": "a", "thing": groups["thing"]}

    @parser.register_event_handler(r"B (?P<thing>\w+)")
    def b(groups, record):
        return {"event": "b", "thing": groups["thing"]}

    assert parser(make_record(msg="A 42")) == {"event": "a", "thing": "42"}
    assert parser(make_record(msg="B xyz")) == {"event": "b", "thing": "xyz"}


def test_first_registered_pattern_wins_on_overlap():
    parser = RegexpEventParser()

    @parser.register_event_handler(r"foo bar")
    def longer(groups, record):
        return {"event": "longer"}

    @parser.register_event_handler(r"foo")
    def shorter(groups, record):
        return {"event": "shorter"}

    assert parser(make_record(msg="foo bar"))["event"] == "longer"


def test_non_participating_optional_group_is_none():
    parser = RegexpEventParser()
    captured = {}

    @parser.register_event_handler(r"x(?:(?P<opt>y)z)?")
    def handler(groups, record):
        captured.update(groups)
        return {"event": "x"}

    parser(make_record(msg="x"))

    assert captured == {"opt": None}


def test_drop_event_raised_by_handler_propagates():
    parser = RegexpEventParser()

    @parser.register_event_handler(r"drop me")
    def handler(groups, record):
        raise DropEvent("not interesting")

    with pytest.raises(DropEvent):
        parser(make_record(msg="drop me"))


def test_register_event_handler_returns_the_wrapped_function():
    parser = RegexpEventParser()

    def handler(groups, record):
        return {"event": "handled"}

    assert parser.register_event_handler(r"whatever")(handler) is handler


def test_registering_after_compilation_raises():
    parser = RegexpEventParser()

    @parser.register_event_handler(r"first (?P<n>\d+)")
    def first(groups, record):
        return {"event": "first", "n": groups["n"]}

    parser(make_record(msg="first 1"))

    with pytest.raises(RuntimeError, match="after the parser has been compiled"):

        @parser.register_event_handler(r"late (?P<n>\d+)")
        def late(groups, record):
            return {"event": "late", "n": groups["n"]}

    # the late handler is not registered, so its messages still fall back
    assert parser(make_record(msg="late 2"))["event"] == "late 2"


def test_invalid_pattern_raises_on_first_parse():
    parser = RegexpEventParser()

    @parser.register_event_handler(r"(?P<event>[unclosed")
    def handler(groups, record):
        return {"event": "handled"}

    with pytest.raises(re.error):
        parser(make_record())


def test_parser_without_handlers_warns_and_falls_back():
    parser = RegexpEventParser()

    with pytest.warns(UserWarning, match="no registered event handlers") as record:
        assert parser(make_record(msg="anything")) == {"event": "anything"}

    # guards the warning's stacklevel: it must be attributed to the caller of the parser, not to l2sl internals
    assert record[0].filename == __file__

    # the warning is emitted once at compilation; later parses reuse the compiled parser
    assert parser(make_record(msg="still nothing")) == {"event": "still nothing"}
