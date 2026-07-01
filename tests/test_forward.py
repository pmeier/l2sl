import logging

import pytest
import structlog

import l2sl
from l2sl._forward import _RecordForwarder


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
