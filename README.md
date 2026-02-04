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

In the most minimal setup, you only need to do add one thing to your logging setup,
preferably after the `structlog.configure()` call:

```python
import l2sl

l2sl.configure_stdlib_log_forwarding()
```

## How do I learn more?

Please have a look at the [documentation](https://l2sl.readthedocs.io/en/stable/).

[`structlog`]: https://www.structlog.org/
