# Investo Developer Role

Use this role for Python implementation, tests, fixtures, and quality gates. This role is adapted from `.claude/agents/investo-developer.md`.

## Locked Stack

- Python 3.11+
- `httpx.AsyncClient`
- `pydantic v2`
- `pytest-asyncio`
- `hypothesis` only for pure functions and serialization round trips
- `defusedxml` for XML
- `bleach` through `_sanitize.strip_html`
- `ruff`, `mypy --strict`, `pytest`

## Source Adapter Pattern

For a new source adapter:

1. Add `src/investo/sources/<name>.py`.
2. Define a class with `@register`, `name: ClassVar[str]`, `category: ClassVar[Category]`, and `async fetch(client, window)`.
3. Use shared helpers: `retry_get`, `strip_html`, `parse_symbol_list`, and `defusedxml`.
4. Update `src/investo/sources/__init__.py` and plugin contract tests.
5. Add offline fixtures under `tests/unit/sources/fixtures/api/<name>/`.
6. Add `httpx.MockTransport` unit tests.

## R-Rules

- R3: Use the injected client; do not instantiate `httpx.AsyncClient` inside adapters.
- R6: Adapter source failures become `SourceFetchError`; programmer errors propagate.
- R7: Use strict UTC window filtering unless an existing documented adapter exception applies.
- R8: `NormalizedItem` fields must be valid; `raw_metadata` is flat `dict[str, str]`.
- R9: Idempotent output for the same source state; no `datetime.now()` for item timestamps.
- R10: Tests are offline and fixture-backed.
- R12: Configurable lists use `INVESTO_<ADAPTER>_<NOUN>` and `parse_symbol_list`.
- R13: Secrets are read at fetch time and never leaked.

## Quality Gate

Run the smallest relevant gate first, then broaden as risk requires:

- `uv run ruff check <files>`
- `uv run ruff format <files>`
- `uv run mypy --strict <src-files-or-package>`
- `uv run pytest <tests> -v`
- `uv run pytest` for regression confirmation when scope warrants it

Never mark a plan step complete with failing tests.

