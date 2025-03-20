import functools
import logging
import re
import secrets
from collections.abc import Mapping
from typing import Any, Callable

from ._core import Parser

RegexpEventHandler = Callable[
    [dict[str, str], logging.LogRecord], tuple[str, dict[str, Any]]
]


def random_valid_identifier() -> str:
    id = f"_{secrets.token_hex(8)}"
    assert id.isidentifier()
    return id


class _RegexpEventParser:
    def __init__(
        self,
        event_handlers: dict[str, tuple[str, RegexpEventHandler]],
        fallback: Parser,
    ) -> None:
        self._pattern, self._event_map = self._compile(event_handlers)
        self._fallback = fallback

    _GROUP_PATTERN = re.compile(r"\(\?P<(?P<group>\w+)>")

    def _compile(
        self, event_handlers: dict[str, tuple[str, RegexpEventHandler]]
    ) -> tuple[re.Pattern[str], dict[str, tuple[dict[str, str], RegexpEventHandler]]]:
        event_patterns: dict[str, str] = {}
        event_map = {}
        for event_id, (event_pattern, event_handler) in event_handlers.items():
            group_map = {
                group: random_valid_identifier()
                for group in self._GROUP_PATTERN.findall(event_pattern)
            }

            event_patterns[event_id] = self._GROUP_PATTERN.sub(
                lambda match: f"(?P<{group_map[match['group']]}>", event_pattern
            )
            event_map[event_id] = (group_map, event_handler)

        pattern = "|".join(
            f"(?P<{event_id}>{pattern})" for event_id, pattern in event_patterns.items()
        )
        pattern = f"({pattern})"

        return re.compile(pattern), event_map

    def __call__(
        self, event: str, record: logging.LogRecord
    ) -> tuple[str, Mapping[str, Any]]:
        match = self._pattern.match(event)
        if not match:
            return self._fallback(event, record)

        groups = match.groupdict()
        group_map, event_handler = next(
            v for id, v in self._event_map.items() if groups[id] is not None
        )

        return event_handler(
            {group: groups[group_id] for group, group_id in group_map.items()}, record
        )


class RegexpEventParser:
    def __init__(self, fallback: Parser | None = None) -> None:
        self._event_handlers: dict[str, tuple[str, RegexpEventHandler]] = {}

        if fallback is None:

            def fallback(
                event: str, record: logging.LogRecord
            ) -> tuple[str, dict[str, Any]]:
                return event, {}

        self._fallback = fallback

    def register_event_handler(
        self, pattern: str
    ) -> Callable[[RegexpEventHandler], RegexpEventHandler]:
        def decorator(eh: RegexpEventHandler) -> RegexpEventHandler:
            self._event_handlers[random_valid_identifier()] = (pattern, eh)
            return eh

        return decorator

    @functools.cached_property
    def _parser(self) -> _RegexpEventParser:
        return _RegexpEventParser(self._event_handlers, self._fallback)

    def __call__(
        self, event: str, record: logging.LogRecord
    ) -> tuple[str, Mapping[str, Any]]:
        return self._parser(event, record)
