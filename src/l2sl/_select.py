__all__ = ["LoggerSelector"]

import functools
from collections.abc import Iterable


class LoggerSelector:
    def __init__(self, available_loggers: Iterable[str]) -> None:
        self._available_loggers = [l.split(".") for l in available_loggers]

    @functools.lru_cache()
    def __call__(self, logger: str) -> str | None:
        l = logger.split(".")
        applicable_loggers = sorted(
            (
                a
                for a in self._available_loggers
                if len(l) >= len(a) and l[: len(a)] == a
            ),
            key=len,
        )
        if not applicable_loggers:
            return None

        # FIXME: does this guaratee that the return is always a member of available loggers?
        return ".".join(applicable_loggers[-1])
