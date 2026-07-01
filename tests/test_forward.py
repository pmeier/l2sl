import logging

import pytest
import structlog

import l2sl
from l2sl._forward import _RecordForwarder


def test_configure_stdlib_log_forwarding_clears_old_handlers():
    foo = logging.getLogger("foo")
    bar = logging.getLogger("foo.bar")
    baz = logging.getLogger("baz")

    foo.addHandler(logging.StreamHandler())
    bar.addHandler(logging.StreamHandler())
    baz.addHandler(logging.StreamHandler())
    logging.root.addHandler(logging.StreamHandler())

    l2sl.configure_stdlib_log_forwarding()

    assert len(logging.root.handlers) == 1
    assert isinstance(logging.root.handlers[0], _RecordForwarder)

    assert foo is logging.getLogger("foo")
    assert len(foo.handlers) == 0
    assert not foo.disabled

    assert bar is logging.getLogger("foo.bar")
    assert len(bar.handlers) == 0
    assert not bar.disabled

    assert baz is logging.getLogger("baz")
    assert len(baz.handlers) == 0
    assert not baz.disabled


def test_configure_stdlib_log_forwarding_unable_to_validate():
    with pytest.raises(RuntimeError, match="not configured"):
        l2sl.configure_stdlib_log_forwarding(validate_structlog_config=True)


def test_configure_stdlib_log_forwarding_not_compatible():
    structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())

    with pytest.raises(RuntimeError, match="not compatible"):
        l2sl.configure_stdlib_log_forwarding()
