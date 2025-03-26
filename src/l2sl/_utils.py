import functools
from collections.abc import Collection


class LoggerSelector:
    def __init__(self, available_loggers: Collection[str]) -> None:
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

        return ".".join(applicable_loggers[-1])
