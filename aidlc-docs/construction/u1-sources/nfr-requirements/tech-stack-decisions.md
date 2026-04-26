# Tech Stack Decisions — `u1 sources`

**Date**: 2026-04-27
**Source**: u1-sources-nfr-requirements-plan.md (all recommended)

This locks `u1`-specific library choices. Project-wide stack
(Python 3.11+, pydantic v2, ruff, mypy --strict, pytest, hypothesis)
is already fixed in `docs/tech-env.md` and `pyproject.toml` and is
not re-decided here.

---

## TS-1. Async HTTP — `httpx>=0.27`

- **Status**: locked at project level (`pyproject.toml` core dep).
- **Used here**: shared `httpx.AsyncClient` injected by `fetch_all`
  (FD R3).
- **Why this and not `aiohttp`**: project rule of thumb is "one HTTP
  library across all units"; `httpx` is already the chosen one for
  notifier (u4) and is friendlier for sync code paths if ever needed.
- **Version floor**: `>=0.27` to get the modern transport / mock
  support used by tests.

---

## TS-2. XML parsing — `defusedxml>=0.7`

- **Status**: NEW dep for this unit (added to `[project.dependencies]`
  in `pyproject.toml` during Code Generation step 1).
- **Used here**: parsing the FOMC RSS Atom feed; any future XML/RSS
  source.
- **Why `defusedxml` and not stdlib `xml.etree.ElementTree`**: stdlib
  parser is vulnerable to XML External Entity (XXE) and billion-laughs
  attacks. `defusedxml` is a drop-in replacement that disables those
  attack vectors. NFR-007 requires it (AC-7.4).
- **Why not `feedparser`**: pulls many transitive deps, has a loose
  parsing mode that silently accepts malformed input — exactly the
  opposite of what we want. We keep one parsing path: `defusedxml`
  for XML feeds, stdlib `json` for JSON APIs.

---

## TS-3. HTML sanitization — `bleach>=6`

- **Status**: NEW dep (added during Code Generation step 1).
- **Used here**: stripping HTML tags from feed-derived titles and
  summaries before they enter `NormalizedItem.title` / `.summary`.
  Configuration: strip ALL tags, leaving plain text only.
- **Why `bleach`**: well-audited, used in Mozilla's tooling, exposes
  a simple `clean(text, tags=[], strip=True)` call. NFR-007 requires
  HTML sanitization at this trust boundary (AC-7.2).
- **Why not regex**: HTML cannot be parsed correctly with regex; this
  is a cliché but a true one. Regex stripping leaves attack vectors.

---

## TS-4. JSON parsing — stdlib `json`

- **Status**: stdlib, no dep change.
- **Used here**: any JSON API adapters (none in v1; future adapters
  for Yahoo/yfinance/CoinGecko/etc. would land here).
- **Why stdlib**: safe by default; no XXE-equivalent vulnerability;
  fast enough for our payload sizes.

---

## TS-5. Logging — stdlib `logging`

- **Status**: stdlib, no dep change.
- **Used here**: `fetch_all` logs WARNING per failed adapter; DEBUG
  per successful adapter (FD L5).
- **Why not `structlog` / `loguru`**: project hasn't standardized on
  a structured-logging library. GitHub Actions log output is
  human-read, not parsed. Defer to a project-wide ADR if/when log
  aggregation is introduced.

---

## TS-6. Time / timezone — stdlib `zoneinfo`

- **Status**: stdlib, no dep change.
- **Used here**: `FetchWindow.from_kst_date` resolves Asia/Seoul to
  fixed UTC+9; in `zoneinfo` this looks like
  `ZoneInfo("Asia/Seoul")`.
- **Why not `pytz`**: `zoneinfo` is the modern stdlib replacement
  (Python 3.9+); we target 3.11+ already.

---

## TS-7. Test deps (no project-level change needed)

- `hypothesis>=6` — already locked; used for AC-6.1/6.2/6.3.
- `pytest-asyncio>=0.23` — already locked; needed for `async def`
  tests on `fetch` and `fetch_all`.
- HTTP mocking: use `httpx.MockTransport` (built into `httpx`); no
  new dep.
- XML/HTML fixture data lives in `tests/fixtures/api/<source_name>/`
  as raw bytes plus a `.meta.json` (status, headers).

---

## Cumulative dependency delta

After Code Generation step 1, `pyproject.toml` `[project.dependencies]`
gains:

```toml
"defusedxml>=0.7",
"bleach>=6",
```

Total adapter unit's external deps after `u1` lands:
`pydantic`, `httpx`, `defusedxml`, `bleach`. Four small, audited,
maintained packages.

---

## Out of scope for this unit

- `feedparser` — explicitly rejected (TS-2)
- `pytz` — superseded by `zoneinfo` (TS-6)
- `structlog`/`loguru` — defer (TS-5)
- HTTP cache (`hishel`, `cachecontrol`) — daily cron, no caching needed
- `asyncio.Semaphore` for global concurrency throttle — adapters are
  few enough that unbounded `gather` is fine in v1
