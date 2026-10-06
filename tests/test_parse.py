import logging
import re
import sys

import pytest
from structlog.exceptions import DropEvent

from l2sl._parse import RegexpEventParser, exc_to_exc_info, safe_fallback_parser


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
