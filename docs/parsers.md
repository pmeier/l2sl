# Parsers

A [l2sl.Parser][] converts a stdlib [logging.LogRecord][] into a [structlog.typing.EventDict][]. This tutorial covers
what `l2sl` does out of the box and how to write your own parsers, both plain and regexp-based.

## What l2sl does by default

After calling [l2sl.configure_stdlib_log_forwarding][] without arguments, every stdlib log record is routed through one
of the bundled parsers, or through [l2sl.safe_fallback_parser][] if no bundled parser matches the record's logger. The
fallback keeps things simple:

- The formatted log message becomes the `event` key.
- Values passed via the `extra` argument of the logging call are included as-is.
- `exc_info` is normalized to the tuple form structlog expects.

```python
import logging

log = logging.getLogger("somewhere")
log.info("hello world", extra={"request_id": "abc123"})
```

turns into

```python
{"event": "hello world", "request_id": "abc123"}
```

This event dict is injected into the structlog pipeline you configured, so your processors and renderer apply to
forwarded records exactly as they do to records logged through structlog directly.

### Bundled parsers

`l2sl` ships parsers for libraries that log through the stdlib `logging` module:

| Library | Captures                                                                      |
| ------- | ----------------------------------------------------------------------------- |
| uvicorn | server lifecycle events (`host`, `port`, `pid`) and access records            |
| httpx   | `method`, `url`, `protocol`, `status_code`                                    |
| tornado | access records: `method`, `endpoint`, `origin`, `status_code`, `elapsed_time` |
| bokeh   | server startup versions, connected clients and sessions                       |
| panel   | session state changes and event processing                                    |

Logger names are matched by the longest registered prefix. A parser registered for `uvicorn` also handles
`uvicorn.error` and `uvicorn.access`, while a parser registered for `uvicorn.error` takes precedence for that exact
logger.

## Writing a plain parser

A [l2sl.Parser][] is any callable that takes a [logging.LogRecord][] and returns a [structlog.typing.EventDict][]. You
have full access to the record, so a parser can pull whatever is useful:

```python
import logging

from structlog.typing import EventDict


def my_lib_parser(record: logging.LogRecord) -> EventDict:
    return {
        "event": record.getMessage(),
        "module": record.module,
        "line": record.lineno,
    }
```

Register it by passing a mapping of logger names to parsers. Note that providing `parsers` replaces the bundled set, so
merge with [l2sl.builtin_parsers][] if you want to keep them:

```python
import l2sl

l2sl.configure_stdlib_log_forwarding(
    parsers=l2sl.builtin_parsers() | {"my_lib": my_lib_parser},
)
```

Two more things a parser can do:

- Raise [structlog.exceptions.DropEvent][] to discard a record entirely.
- If a parser raises any other exception, the record is not lost: it goes to the fallback parser, and the failure itself
  is logged under the `l2sl` logger with a `l2sl_parser_error_id` (a UUID) that links the error to the record.

### Unpacking format arguments

A parser that reads `record.args` positionally should not unpack it directly: a library that changes one of its log
calls turns into a bare `ValueError: not enough values to unpack` in the middle of the pipeline.
[l2sl.expect_tuple_args][] checks the shape first and returns the arguments, raising [l2sl.ParserArgsError][] when they
differ:

```python
import logging

from structlog.typing import EventDict

from l2sl import expect_tuple_args


def my_lib_parser(record: logging.LogRecord) -> EventDict:
    method, url = expect_tuple_args(record, 2)
    return {"event": "request", "method": method, "url": url}
```

The failure message names the logger and both counts, and the error carries the offending record on its `record`
attribute:

```
Expected 2 positional format arguments for logger 'my_lib', got 3: ('GET', 'http://x', 'extra')
```

Records that pass their arguments as a mapping (`logger.info("%(name)s", {...})`) have no positional shape, so they are
reported as a mismatch instead of being converted. As with any other parser failure, the record still reaches the
fallback parser and the message becomes the `reason` of the `using safe fallback parser` error log.

## Writing a regexp parser

For libraries that log free-form text, [l2sl.RegexpEventParser][] dispatches on the message itself. Create one and
decorate event handlers with [l2sl.RegexpEventParser.register_event_handler][]. Each pattern may contain named groups
that are handed to the handler as a dict.

Consider a library that logs requests as

```
200 GET /index (127.0.0.1) 1.23ms
```

A parser for it looks like this:

```python
import logging

from structlog.typing import EventDict

from l2sl import RegexpEventParser

parser = RegexpEventParser()


@parser.register_event_handler(
    r"(?P<status_code>\d{3}) (?P<method>[A-Z]+) (?P<endpoint>\S+) \((?P<origin>[^)]+)\) (?P<elapsed_time>\d+\.\d+)ms"
)
def request(
    groups: dict[str, str], record: logging.LogRecord
) -> EventDict:
    elapsed_time = float(groups.pop("elapsed_time"))
    return {"event": "request", "elapsed_time": elapsed_time / 1e3} | groups
```

The handler receives the captured groups plus the original record, so it can convert types (`elapsed_time` becomes a
float in seconds) and add fixed keys like `event`. Register the parser the same way as a plain one:

```python
l2sl.configure_stdlib_log_forwarding(
    parsers=l2sl.builtin_parsers() | {"my_lib.access": parser},
)
```

The event dict this handler returns is injected into the structlog pipeline you configured:

```python
{
    "event": "request",
    "status_code": "200",
    "method": "GET",
    "endpoint": "/index",
    "origin": "127.0.0.1",
    "elapsed_time": 0.00123,
}
```

What the final log output looks like depends on the processors and renderer in your structlog configuration, not on
l2sl.

Messages that match no registered pattern go to the parser's own fallback, which defaults to
[l2sl.safe_fallback_parser][] and can be overridden via the `fallback` argument of [l2sl.RegexpEventParser][]. All
patterns are compiled into a single alternation before the first call, so registration must happen before the parser is
used.
