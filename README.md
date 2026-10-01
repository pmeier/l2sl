# l2sl

## What is this?

`l2sl` funnels log records of third-party tools into your [`structlog`] pipeline. In
addition, `l2sl` converts the text based log records into a structured representation.

## Why do I need it?

You need `l2sl` if

- you are using [`structlog`] as the logging library in your application,
- you depend on third-party libraries, e.g.
  [`uvicorn`](https://github.com/Kludex/uvicorn) or
  [`httpx`](https://github.com/encode/httpx), that use the `logging` module from the
  standard library for logging, as they should, and
- you want the log records from the third-party libraries processed by the same
  [`structlog`] pipeline as your own log records.

## Why not use `structlog.stdlib`?

Because that is the opposite of [what you need](#why-do-i-need-it) if you have read
until here.
[`structlog`'s standard library integration](https://www.structlog.org/en/stable/standard-library.html)
helps integrating a [`structlog`] pipeline into an existing stdlib logging pipeline.
`l2sl` let's you define the whole pipeline in [`structlog`] without the need to ever
touch stdlib logging including for any third-party libraries outside of your control
that use it.

The two setups are mutually exclusive: `l2sl` rejects a [`structlog`] configuration that
is configured for stdlib logging, since both want to own the output side of the
pipeline.

## How do I get started?

In the most minimal setup, you only need to do add one thing to your logging setup,
preferably after the `structlog.configure()` call:

```python
import l2sl

l2sl.configure_stdlib_log_forwarding()
```

## How do I learn more?

Please have a look at the [documentation](https://l2sl.readthedocs.io/stable/).

[`structlog`]: https://www.structlog.org/
