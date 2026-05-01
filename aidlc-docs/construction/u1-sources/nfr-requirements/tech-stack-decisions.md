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

## TS-8. Source-specific configuration — env vars + stdlib `os` (extension 2026-05-01)

- **Status**: stdlib (`os.environ`); no dep change.
- **Used here**: yfinance / CoinGecko / FRED adapters expose configurable
  symbol/coin/series lists via env vars per FD R12. Shared parser at
  `src/investo/sources/_config.py` (added in extension Step 1) handles
  comma-split, whitespace-strip, empty-token-drop, fall-through-to-defaults.
- **Why env vars and not a YAML config file**: zero-touch operation
  for the 1-person operator. Cron lives in
  `.github/workflows/daily-briefing.yml` already; the operator edits
  one file (the workflow YAML) when they want non-default coverage.
  A second `config.yaml` would mean two files to keep in sync and
  one more thing to forget when adding a new adapter.
- **Why not pydantic Settings / dynaconf**: overkill for ≤10 string
  lists. The shared parser is ~20 lines.
- **Defaults visible to reviewers**: each adapter exposes its
  defaults as a module-level
  `_DEFAULT_<NOUN>: Final[tuple[str, ...]]` constant. Reviewers see
  exactly what the adapter will fetch on a default-config run.

---

## TS-9. FRED API key — env var + GitHub Secrets (extension 2026-05-01)

- **Status**: stdlib `os.environ`; no dep change.
- **Used here**: FRED adapter reads `FRED_API_KEY` at fetch time.
  Missing → `SourceFetchError(transient=False)` per FD R13.
- **Storage**: GitHub Secrets (`FRED_API_KEY`); injected to runner
  via `daily-briefing.yml` `env:` block — same pattern as the existing
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BRIEFING_CHANNEL_ID`,
  `TELEGRAM_OPERATOR_CHAT_ID`, `CLAUDE_CODE_OAUTH_TOKEN`.
- **Why not a `.env` file**: secrets must not appear in the repo. The
  GitHub Secret value is masked in workflow logs by GHA.
- **Why not pydantic Settings**: same reason as TS-8 — overkill for
  one string.
- **Failure surface stays in the adapter**: u5 orchestrator does NOT
  pre-check `FRED_API_KEY` at boot. R13 keeps the failure isolation
  contract (R6) pure: missing secret looks identical to source 5xx
  to the aggregator.

---

## TS-10. Yahoo Finance access — direct httpx, not the `yfinance` library (extension 2026-05-01)

- **Status**: explicit reject of the python `yfinance` package.
- **Decision** (Q1=B, audit log 2026-05-01): yfinance v8 chart API
  reached via direct `httpx` GET in
  `src/investo/sources/yfinance.py`, identical pattern to the
  FOMC RSS adapter. No new dep.
- **Why not the `yfinance` library**:
  1. **Sync-only.** `yfinance.Ticker(...).history(...)` blocks the
     event loop. Wrapping in `asyncio.to_thread` works but breaks
     FD R3 (shared `httpx.AsyncClient` injection — the library
     creates its own `requests.Session`, defeating the connection
     pool).
  2. **Hidden cache + retry policy.** Library has its own retry/
     timeout logic that conflicts with our shared `retry_get`
     (FD R4). Two retry layers stacked = harder to reason about.
  3. **Schema fragility.** The library scrapes Yahoo's web pages in
     several code paths and breaks on layout changes (well-documented
     in its issue tracker). Direct v8-chart API call is more stable.
  4. **Transitive deps.** The library pulls `pandas`, `numpy`,
     `requests`, `beautifulsoup4`, `lxml`, `multitasking`,
     `frozendict`, `peewee` — all unnecessary for "give me yesterday's
     close".
- **Why direct httpx is fine**: the v8 chart endpoint
  (`https://query1.finance.yahoo.com/v8/finance/chart/{ticker}`)
  is the same endpoint the `yfinance` library hits internally. The
  response is plain JSON. Our `retry_get` already handles 429 / 5xx
  / timeouts.

---

## Cumulative dependency delta

After original Code Generation step 1 (2026-04-29), `pyproject.toml`
`[project.dependencies]` gains:

```toml
"defusedxml>=0.7",
"bleach>=6",
```

**Extension 2026-05-01**: zero new deps. yfinance / CoinGecko / FRED
adapters reuse `httpx` (TS-1), stdlib `json` (TS-4), stdlib `zoneinfo`
(TS-6), stdlib `os` (TS-8 / TS-9). Reject of the `yfinance` library
(TS-10) is the deliberate choice that keeps the dep delta empty.

Total adapter unit's external deps after extension lands:
`pydantic`, `httpx`, `defusedxml`, `bleach` — unchanged from the
post-Step-1 baseline. Four small, audited, maintained packages.

---

## Out of scope for this unit

- `feedparser` — explicitly rejected (TS-2)
- `pytz` — superseded by `zoneinfo` (TS-6)
- `structlog`/`loguru` — defer (TS-5)
- HTTP cache (`hishel`, `cachecontrol`) — daily cron, no caching needed
- `asyncio.Semaphore` for global concurrency throttle — adapters are
  few enough that unbounded `gather` is fine in v1
- `yfinance` library — explicitly rejected (TS-10)
- `pycoingecko` library — same family of objections as `yfinance`
  (sync-only `requests`-based wrapper around endpoints we can call
  directly); not needed for our 1-call-per-fetch usage
- `fredapi` library — same; FRED's REST API is trivial to call
  directly
