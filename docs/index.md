# l2sl

## What is this?

`l2sl` funnels log records of third-party tools into your [structlog] pipeline. In
addition, `l2sl` converts the text based log records into a structured representation.

## Why do I need it?

You need `l2sl` if

- you are using [structlog] as the logging library in your application,
- you depend on third-party libraries, e.g.
  [`uvicorn`](https://github.com/Kludex/uvicorn) or
  [`httpx`](https://github.com/encode/httpx), that use the `logging` module from the
  standard library for logging, and
- you want the log records from the third-party libraries processed by the same
  [structlog] pipeline as your own log records.

[structlog]: https://www.structlog.org/
