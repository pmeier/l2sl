# l2sl

## What is this?

`l2sl` funnels log records of third-party tools into your [`structlog`] pipeline. In
addition, `l2sl` converts the text based log records into a structured representation.

## Why do I need it?

You need `l2sl` if

- you are using [`structlog`] as the logging library in your application,
- you depend on third-party libraries, e.g.
  [`uvicorn`](https://github.com/encode/uvicorn) or
  [`httpx`](https://github.com/encode/httpx), that use the `logging` module from the
  standard library for logging, and
- you want the log records from the third-party libraries processed by the same
  [`structlog`] pipeline as your own log records.

## How do I get started?

In the most minimal setup, you only need change two things:

1. Add the `l2sl.StdlibRecordParser()` to the list of `processors` in
   `structlog.configure`.
2. Call `l2sl.configure_stdlib_logging()` after you are done configuring `structlog`.

```python
import l2sl
import structlog

structlog.configure(
    processors=[
        l2sl.StdlibRecordParser(),
        ...,
    ],
    ...,
)

l2sl.configure_stdlib_logging()
```

## How do I learn more?

Please have a look at the [documentation](https://l2sl.readthedocs.io/en/stable/).

[`structlog`]: https://www.structlog.org/
