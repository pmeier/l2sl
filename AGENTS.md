# AGENTS.md

## Project overview

`l2sl` ("logging to structured logging") is a small Python library that forwards
`logging` (stdlib) records from third-party libraries into a
[`structlog`](https://www.structlog.org/) pipeline and converts their text messages into
structured events via parsers.

- Package: `src/l2sl/` (src layout), distributed on PyPI as `l2sl`
- Supported Python: 3.10+ (`.python-version` pins 3.10 for local dev)
- Runtime deps: `structlog`, `typing-extensions` (only for Python < 3.11)
- Docs: `docs/` + `mkdocs.yml`, published at https://l2sl.readthedocs.io/en/stable/

Key entry points (see `src/l2sl/__init__.py`):

- `l2sl.configure_stdlib_log_forwarding()` — installs the `_RecordForwarder` handler on
  the root logger and clears existing handlers.
- `l2sl.Parser` / `RegexpEventParser` / `RegexpEventHandler` — parsing machinery in
  `_parse.py`.
- `l2sl.builtin_parsers` — per-library parsers in `src/l2sl/_builtin_parsers/` (uvicorn,
  tornado, httpx, bokeh, panel, neo4j).

## Tooling

Everything runs through `uv` (pinned via `.mise.toml`). Use `uv run <tool>` for all
commands. The virtualenv lives in `.venv/`.

| Task                         | Command                                                            |
| ---------------------------- | ------------------------------------------------------------------ |
| Install/sync deps            | `uv sync`                                                          |
| Run tests                    | `uv run pytest`                                                    |
| Single test                  | `uv run pytest tests/test_forward.py::test_name`                   |
| Coverage (as CI does)        | `uv run pytest --cov l2sl --cov ./tests --cov-report term-missing` |
| Type checking                | `uv run mypy`                                                      |
| Format + lint (staged files) | `uv run pre-commit run --all-files`                                |
| Build distributions          | `uv build`                                                         |
| Docs locally                 | `uv run mkdocs serve`                                              |

## Code style

- **Formatting**: `ruff format` (plus `prettier` for markdown/toml via pre-commit).
- **Linting**: ruff with `E`, `F`, `I001` selected; `E501` (line length) and `E741`
  ignored.
- **Typing**: mypy is strict for `src/l2sl` — `disallow_untyped_calls`,
  `disallow_untyped_defs`, `disallow_incomplete_defs`, `warn_unused_ignores`,
  `warn_return_any`. All public and private functions in the package need full
  annotations. The package ships `py.typed`.
- Version is managed by `setuptools_scm`; `src/l2sl/_version.py` is generated — never
  edit it by hand.

## Tests

- Location: `tests/`, mirroring the module under test (`test_forward.py` →
  `_forward.py`, etc.).
- `filterwarnings = ["error"]` (except `ResourceWarning`): any warning raised during a
  test fails the run. `xfail_strict = true`.
- Tests may poke at private APIs (e.g. `l2sl._forward._RecordForwarder`); this is fine
  internally, but public behavior changes should be reflected in `__all__` and the docs.

## CI expectations

GitHub Actions runs on PRs: `lint.yml` (pre-commit on changed files + mypy), `test.yml`
(pytest with coverage on Ubuntu/Windows/macOS, Python 3.11–3.14), `build.yml`
(`uv build`). Code must pass all of these before a PR is ready.
