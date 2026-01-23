import json
import operator

import pydantic
import pytest

from l2sl import LogLevel


class TestLogLevel:
    @pytest.mark.parametrize(
        ("type", "value"),
        [
            *[("number", v) for v in LogLevel._NUMBER_TO_STDLIB_NAME],
            *[("stdlib_name", v) for v in LogLevel._STDLIB_NAME_TO_NUMBER],
            *[("structlog_name", v) for v in LogLevel._STRUCTLOG_NAME_TO_STDLIB_NAME],
        ],
    )
    def test_parsing(self, type, value):
        log_level = LogLevel(value)
        assert getattr(log_level, type) == value

    @pytest.mark.parametrize(
        ("a", "op", "b"),
        [
            ("info", operator.lt, "warning"),
            ("info", operator.lt, "WARNING"),
            ("info", operator.lt, 30),
            ("info", operator.eq, "info"),
            ("info", operator.eq, "INFO"),
            ("info", operator.eq, 20),
            ("info", operator.gt, "debug"),
            ("info", operator.gt, "DEBUG"),
            ("info", operator.gt, 10),
        ],
    )
    @pytest.mark.parametrize("as_log_level", ["left", "right", "both"])
    def test_comparison(self, a, op, b, as_log_level):
        match as_log_level:
            case "left":
                a = LogLevel(a)
            case "right":
                b = LogLevel(b)
            case "both":
                a = LogLevel(a)
                b = LogLevel(b)
            case _:
                raise ValueError(f"{as_log_level=}")

        assert op(a, b)

    @pytest.mark.parametrize("level", ["info", "INFO", 20])
    def test_str(self, level):
        log_level = LogLevel(level)
        assert str(log_level) == log_level.stdlib_name

    @pytest.mark.parametrize("level", ["info", "INFO", 20])
    def test_repr_smoke(self, level):
        repr(level)

    @pytest.mark.parametrize("level", ["info", "INFO", 20, LogLevel("info")])
    def test_pydantic_validate_python(self, level):
        log_level = level if isinstance(level, LogLevel) else LogLevel(level)

        ta = pydantic.TypeAdapter(LogLevel)
        assert ta.validate_python(level) == log_level

    def test_pydantic_dump_python(self):
        log_level = LogLevel("info")

        ta = pydantic.TypeAdapter(LogLevel)
        assert ta.dump_python(log_level) == str(log_level)

    @pytest.mark.parametrize("level", ["info", "INFO", 20])
    def test_int(self, level):
        log_level = LogLevel(level)
        assert int(log_level) == log_level.number

    @pytest.mark.parametrize("level", ["info", "INFO", 20])
    def test_pydantic_validate_json(self, level):
        log_level = LogLevel(level)

        ta = pydantic.TypeAdapter(LogLevel)
        assert ta.validate_json(json.dumps(level)) == log_level

    def test_pydantic_dump_json(self):
        log_level = LogLevel("info")

        ta = pydantic.TypeAdapter(LogLevel)
        assert ta.dump_json(log_level) == json.dumps(str(log_level)).encode()
