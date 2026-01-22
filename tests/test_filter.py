import logging

import pytest

from l2sl import SimpleRecordFilter


def new_record(name, level):
    return logging.LogRecord(
        name, SimpleRecordFilter._log_level_to_number(level), "", 0, "", None, None
    )


class TestSimpleRecordFilter:
    @pytest.mark.parametrize(
        ("loggers", "default_level", "record", "expected"),
        [
            (["foo", "bar"], "info", new_record("foo", "info"), True),
            (["foo", "bar"], "warn", new_record("foo", "info"), False),
            (["foo", "bar"], "info", new_record("bar", "debug"), False),
            ({"foo": "info", "bar": "warn"}, None, new_record("foo", "warn"), True),
            ({"foo": "info", "bar": "warn"}, None, new_record("bar", "info"), False),
            (["foo", "bar"], "info", new_record("foo.boo", "info"), True),
            (["foo.boo", "bar"], "info", new_record("foo", "info"), False),
            (["foo", "bar"], "info", new_record("foo.boo", "info"), True),
        ],
    )
    def test_include(self, loggers, default_level, record, expected):
        record_filter = SimpleRecordFilter.include(loggers, default_level=default_level)
        assert record_filter(record) == expected

    @pytest.mark.parametrize("default_level", [0, "DEBUG", "warn"])
    def test_include_unused_default_log_level_for_mapping(self, default_level):
        with pytest.raises(ValueError, match="default_level must not be set"):
            SimpleRecordFilter.include({}, default_level=default_level)

    @pytest.mark.parametrize(
        ("loggers", "default_level", "record", "expected"),
        [
            (["foo", "bar"], "info", new_record("baz", "info"), True),
            (["foo", "bar"], "warn", new_record("baz", "info"), False),
            (["foo.boo", "bar"], "info", new_record("foo", "info"), True),
            (["foo.boo", "bar"], "info", new_record("foo", "debug"), False),
            (["foo.boo", "bar"], "info", new_record("foo.boo", "info"), False),
        ],
    )
    def test_exclude(self, loggers, default_level, record, expected):
        record_filter = SimpleRecordFilter.exclude(loggers, default_level=default_level)
        assert record_filter(record) == expected
