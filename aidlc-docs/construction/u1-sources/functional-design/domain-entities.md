# Domain Entities — `u1 sources`

**Date**: 2026-04-27
**Source**: u1-sources-functional-design-plan.md (all recommended)

This unit's domain is the **collection layer**: external sources, the
plugin contract, the in-pipeline data shape, and the unit's own error
type. Pydantic models that cross unit boundaries (`NormalizedItem`)
already live in the foundation library and are *consumed* — this
document focuses on entities that originate inside `sources`.

---

## E1. SourceAdapter (Protocol)

**Kind**: Protocol class (structural typing). Imported by all adapters.

**Identity**: Each adapter is identified by `name`, a short stable
slug. Two adapters with the same `name` is a programmer error and the
registry must reject it on import.

**Attributes**:

| Field | Type | Constraint |
|-------|------|-----------|
| `name` | `str` | unique within registry; slug-shaped (`a-z0-9-`); set as a class attribute, not instance |
| `category` | `Category` | one of the 5 literals defined in `models.items` |

**Behaviour**:

- `async def fetch(client: httpx.AsyncClient, target_date: date) -> list[NormalizedItem]`
- May raise `SourceFetchError` (and only this) for retriable / source-side failures. Programmer errors propagate as ordinary exceptions and surface to the orchestrator.

**Lifecycle**: Stateless — adapters do not hold sockets, files, or DB
handles. The shared `AsyncClient` is injected per call (Q2=A).

---

## E2. SourceRegistry (module-level singleton)

**Kind**: Internal mutable mapping (`dict[str, SourceAdapter]`) hidden
behind `register(...)` and `list_sources()` accessors.

**Population**: At import time. `sources/__init__.py` imports every
`sources/<adapter>.py` so each module's `@register` decorator runs as
a side effect. There is no runtime discovery step.

**Invariants**:
- Names are unique. Re-registration raises `RuntimeError` (config bug).
- The registry is never mutated after `sources/__init__.py` finishes
  importing. Tests may use a fixture to monkeypatch it for a single
  case but must restore the original.

**Why a module-level singleton** rather than a class? The registry has
no per-instance state; an instance would complicate adapter authoring
("which registry?") for no gain. A single registry per process matches
the deployment model (one cron run = one process).

---

## E3. FetchWindow (value object — *internal* to sources)

**Kind**: Frozen dataclass (or pydantic if convenient) inside
`sources/_window.py`. Not part of the public surface; not re-exported.

| Field | Type |
|-------|------|
| `start_utc` | `datetime` (tz-aware) |
| `end_utc` | `datetime` (tz-aware) |
| `target_date` | `date` (the KST trading date this window represents) |

**Why a value object**: Q6=A says adapters filter on a UTC window.
Computing the window from `target_date` is a single function call
that all adapters share. Putting it in a value object means the
aggregator (or future orchestrator-side helper) builds it once and
hands it off, instead of each adapter recomputing. It also makes
testing trivial — pass a constructed `FetchWindow` instead of mocking
clocks.

**Construction**: `FetchWindow.from_kst_date(target_date)` returns
`FetchWindow(start_utc=..., end_utc=...)` covering the KST midnight-
to-midnight span (Asia/Seoul). The start is `target_date 00:00 KST`,
end is `(target_date + 1) 00:00 KST`, both expressed in UTC. KST is
fixed UTC+9 with no DST so this is unambiguous.

---

## E4. SourceFetchError (exception)

**Kind**: Custom exception class.

**Hierarchy**: subclass of `Exception` (not `RuntimeError`) so test
fixtures can `pytest.raises(SourceFetchError)` without catching
unrelated runtime errors.

**Attributes**:

| Attr | Type | Required |
|------|------|----------|
| `source_name` | `str` | yes |
| `cause` | `BaseException \| None` | no — set to original exception when raised from a wrapper |
| `transient` | `bool` | yes — `True` for retried-and-still-failed (timeout, 5xx, 429); `False` for terminal (4xx-not-429, schema decode) |

**Construction examples**:
- Connection timed out after 2 retries: `SourceFetchError("fomc-rss", cause=httpx.TimeoutException(...), transient=True)`
- Source returned malformed XML: `SourceFetchError("fomc-rss", cause=ValueError(...), transient=False)`

The `transient` flag is for the operator log message — it does NOT
affect aggregator behaviour (both are caught and logged the same way
per Q4=A).

---

## E5. AggregatorResult (return shape — implicit)

`fetch_all(target_date)` returns `list[NormalizedItem]`. There is no
wrapper type; the aggregator simply concatenates per-adapter results
and drops empties from failed adapters. Failures are recorded in the
process log, not in the return value (Q4=A).

If the *entire* run yields zero items, the orchestrator (not this
unit) is responsible for treating that as a pipeline-level failure
guard.

---

## Entity dependency graph

```
                    +-------------------+
                    |  models.items     |
                    | (NormalizedItem,  |
                    |  Category)        |
                    +---------+---------+
                              |
                              v
              +-------------------------------+
              |  SourceAdapter Protocol (E1)  |
              +---------------+---------------+
                              |
              implemented by  v
              +-------------------------------+
              |  per-source adapter classes   |
              |  (e.g. FomcRssAdapter)        |
              +-------------------------------+
                              ^
                              | registered into
              +---------------+---------------+
              |  SourceRegistry (E2)          |
              +---------------+---------------+
                              ^
                              | iterates
              +---------------+---------------+
              |  fetch_all(target_date)       |
              +---------------+---------------+
                              |
                              | uses
                              v
              +-------------------------------+
              |  FetchWindow (E3)             |
              +-------------------------------+

  Errors flow upward as SourceFetchError (E4),
  caught at fetch_all and logged, never re-raised.
```

---

## What lives outside this unit

- `NormalizedItem`, `Category`, `HttpUrl` types — `investo.models`
- `httpx.AsyncClient` — third-party; injected, not constructed here
- The 4-min collect time budget — orchestrator enforces, not this unit
- The KST-vs-UTC date conversion of `target_date` arrival — done in
  the orchestrator's `resolve_target_date`; this unit receives the
  already-resolved `date` and only computes the UTC window (E3)
