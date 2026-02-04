import pytest
import structlog

import l2sl


def test_configure_stdlib_log_forwarding_unable_to_validate():
    with pytest.raises(RuntimeError, match="not configured"):
        l2sl.configure_stdlib_log_forwarding(validate_structlog_config=True)


def test_configure_stdlib_log_forwarding_not_compatible():
    structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())

    with pytest.raises(RuntimeError, match="not compatible"):
        l2sl.configure_stdlib_log_forwarding()
