# Contributing to Investo

This is a 1-person automation tool, but the discipline below keeps
the codebase debuggable for the future-you who has to revive it
after a long break.

---

## Adding a new data source

The plugin contract (US-008, NFR AC-5.4) is a **4-step procedure**:

1. **Create** `src/investo/sources/<name>.py` (e.g., `treasury_yield.py`).
2. **Define** an adapter class with class attributes
   - `name: ClassVar[str]` — slug, unique across all adapters (e.g. `"treasury-yield"`)
   - `category: ClassVar[Category]` — one of `news`, `price`, `macro`, `calendar`, `earnings`
   - `async def fetch(self, client: httpx.AsyncClient, window: FetchWindow) -> list[NormalizedItem]`
3. **Apply** `@register` at class definition (top-of-class decorator, not on a method).
4. **Add** `from . import <name>  # noqa: F401` to
   `src/investo/sources/__init__.py` so the decorator runs at package import time.

Then bump `EXPECTED_ADAPTER_COUNT` and `EXPECTED_ADAPTER_NAMES` in
`tests/unit/sources/test_plugin_contract.py` together. The drift
guard test will fail loudly if you forget — that's the safety net.

### Inside `fetch`

Adapters MUST use the shared retry helper instead of raw `client.get`:

```python
from investo.sources._retry import retry_get

async def fetch(self, client, window):
    response = await retry_get(client, self._FEED_URL, source_name=self.name)
    # ... parse response.content, build NormalizedItem list, filter by window.contains() ...
    return items
```

Adapters MUST sanitize feed-derived text via `_sanitize.strip_html`
(NFR-007 AC-7.2) and MUST parse XML via `defusedxml`, never stdlib
(AC-7.6 — enforced by `tests/unit/sources/test_xml_safety.py` grep).

### Configurable symbol / coin / series lists (R12)

Adapters that expose a list of tickers / coins / series ids the
operator may want to override at runtime use the shared parser
in `investo.sources._config`:

```python
from typing import ClassVar, Final
from investo.sources._config import parse_symbol_list

class MyPriceAdapter:
    name: ClassVar[str] = "my-price"
    category: ClassVar[Category] = "price"

    _DEFAULT_SYMBOLS: ClassVar[tuple[str, ...]] = ("AAPL", "MSFT")

    async def fetch(self, client, window):
        symbols = parse_symbol_list("INVESTO_MY_SYMBOLS", self._DEFAULT_SYMBOLS)
        # ... fetch per symbol ...
```

Convention (FD R12):

- Env var name: `INVESTO_<ADAPTER_SHORT>_<NOUN>` —
  uppercased, no `_price` / `_macro` suffix on the adapter slug.
  Examples in the codebase: `INVESTO_YFINANCE_TICKERS`,
  `INVESTO_COINGECKO_COINS`, `INVESTO_FRED_SERIES`.
- Format: comma-separated, whitespace-trimmed, empty tokens dropped.
- Defaults live in the module as a `_DEFAULT_<NOUN>: Final[tuple[str, ...]]`
  constant. Reviewers see exactly what runs on a default-config run.
- Defaults MUST satisfy NFR-002 (free tier only).
- The parser falls back to defaults when the env var is unset or
  yields zero non-empty tokens — never raises on parse failure.

### Adapters that need an authentication secret (R13)

Adapters that require a per-deployment secret (currently only
`fred-macro` with `FRED_API_KEY`) follow this pattern:

```python
import os
from investo.sources.protocol import SourceFetchError

class MySecretAdapter:
    name: ClassVar[str] = "my-secret"

    async def fetch(self, client, window):
        api_key = os.environ.get("MY_SECRET", "")
        if not api_key:
            raise SourceFetchError(
                source_name=self.name,
                message=f"MY_SECRET not set; {self.name} adapter will not run",
                transient=False,
                cause=None,
            )
        # ... use api_key in request params; never log it ...
```

Rules (FD R13):

- Read the secret at **fetch time**, not at module import (so the
  test suite imports without requiring a live secret).
- Missing or empty secret → `SourceFetchError(transient=False)`.
  The aggregator catches per R6 and logs WARNING; other adapters
  continue. Do NOT pre-check secrets in `__main__._validate_env`
  (R13 keeps the failure surface uniform with all other source-side
  failures).
- Error messages MUST name the env var, NEVER any partial/full
  secret value. Test with a sentinel value (e.g.
  `"REDACTED_KEY_VALUE_12345"`) and assert it never appears in
  `str(error)`, `raw_metadata`, or any captured log line.
- Secret values MUST NOT appear in `raw_metadata`, recorded
  fixtures, or any committed file.
- After adding a secret-using adapter, **update
  `.github/workflows/daily-briefing.yml`** to inject the secret
  into the `python -m investo` step's `env:` block. CI cannot
  inject what the workflow file doesn't ask for.

The `fred-macro` adapter at `src/investo/sources/fred.py` is the
canonical reference for both R12 (`INVESTO_FRED_SERIES`) and R13
(`FRED_API_KEY`).

---

## Recording a fixture

Adapter tests run **offline** (`business-rules.md` R10). For each new
adapter, capture a real response once and commit it:

```bash
mkdir -p tests/unit/sources/fixtures/api/<name>
curl -sS \
  -D /tmp/<name>-headers.txt \
  -o tests/unit/sources/fixtures/api/<name>/feed.xml \
  -A "investo-fixture-recorder/0.1" \
  "<source-url>"
```

Save a `meta.json` next to the fixture with `status`, key headers,
and a `_recorded_at` timestamp. Then write tests using
`httpx.MockTransport` to replay the bytes — never call the real URL
from a test.

If the live feed structure changes and old tests start failing,
re-record the fixture and document the structural diff in
`aidlc-docs/audit.md` (see Step 8 of the u1 sources code-generation
plan for an example: the FOMC feed turned out to be RSS 2.0, not
Atom 1.0 as the FD originally predicted).

---

## Briefing prompts

Stage 1 (classification) and Stage 2 (synthesis) prompt bodies for
the Claude Code CLI live in **exactly one place**:
`src/investo/briefing/prompts.py`. Four module-level constants own
the contract:

- `STAGE1_SYSTEM` — Korean classifier role + JSON schema legend.
- `STAGE1_USER_TEMPLATE` — single placeholder `{items_json}`.
- `STAGE2_SYSTEM` — Korean writer role + 6-section header rules + R8
  Korean-prose-with-English-tickers rule + R6 PII-leak prompt-side hint.
- `STAGE2_USER_TEMPLATE` — `{grouped_sections}` / `{unassigned}` /
  `{target_date}` placeholders.
- `STAGE2_SECTION_HEADERS` — the six fixed `## ① ...` → `## ⑥ ...`
  header strings, re-imported by `pipeline.parse_six_sections` so the
  prompt-side instruction and the parse-side anchor share a single
  source of truth.

**Forbidden** (CI-pinned by
`tests/unit/briefing/test_pipeline_no_prompt_strings.py` and
`tests/unit/briefing/test_prompts.py`):

- Inlining a prompt-body sentinel substring (e.g.
  `"market-briefing classifier"`, `"Pre-grouped items"`,
  `"Section ID legend"`) in any other module under
  `src/investo/briefing/` — pinned by AST-stripped sentinel grep on
  `pipeline.py` and `claude_code.py`.
- Calling `.format(...)` on the SYSTEM constants. They contain
  literal `{` / `}` characters in the JSON-schema example and would
  raise `KeyError`.
- Constructing prompts via f-string interpolation in caller code —
  use the templates' `.format(**kwargs)` so placeholders are
  explicit and reviewable.

If you need to evolve the prompts, edit `prompts.py` only, then
re-record any LLM fixtures whose hashes shift (see next section).

---

## LLM fixture refresh

The briefing pipeline's integration + replay tests use recorded
`claude` CLI outputs keyed by `sha256(prompt)[:16]`, stored under
`tests/fixtures/llm/`. To record fresh fixtures (after a prompt
change, model rev, or new test scenario):

```bash
INVESTO_LIVE_LLM=1 pytest tests/integration/test_briefing_pipeline_poc.py
# (or any test that drives the FakeClaudeRunner via this env var)
```

The runner detects `INVESTO_LIVE_LLM=1`, dispatches the real `claude`
subprocess for cache misses, and atomically writes
`tests/fixtures/llm/<sha256>.json` containing
`{prompt, stdout, stderr, returncode, elapsed_s}`. CI runs in pure
replay mode (`INVESTO_LIVE_LLM` unset) — a missing fixture fails
loudly with the prompt prefix and the expected fixture path so the
fix is obvious.

**Commit** the new `<key>.json` files. They are versioned alongside
the test that depends on them. Do NOT commit `INVESTO_LIVE_LLM=1` to
any CI config or env file — fixture recording is a manual developer
step, not a CI behavior.

If the prompt changes (`prompts.py` edit) but the assertion still
holds, the old fixture key becomes orphaned. Delete the orphan
manually; there is no automatic GC.

---

## Cross-platform notes

Investo is developed on macOS and runs in Linux GitHub Actions, but
the repository contains one git symlink: `site_docs/archive` points to
`../archive` so MkDocs can include the generated briefing archive.

On Windows, git only checks out symlinks as real symlinks when
`core.symlinks=true` and the shell has permission to create them
(Developer Mode or administrator privileges). Without that setup,
`site_docs/archive` may appear as a small text file containing
`../archive`; local MkDocs archive navigation can fail even though the
Linux CI build is fine.

Windows contributors should enable Developer Mode before cloning, or
run:

```bash
git config --global core.symlinks true
```

Then clone the repository again so the symlink is materialized
correctly.

---

## PR description checklist

### Source adapters

Every PR adding or touching a Source Adapter must declare the cost
profile (NFR-002 AC-2.4):

- [ ] **Source URL**: `<https://...>`
- [ ] **Auth**: none / API key / OAuth (specify which)
- [ ] **Free-tier rate limit**: e.g. `60 req/min`
- [ ] **No paid tier required**: confirmed (no billing account, no
      free-trial-then-charge pattern)

Reviewers reject PRs that fail the declaration. The CI cost guard
(`scripts/check_no_paid_apis.py`, run by
`tests/unit/sources/test_no_paid_apis.py`) blocks the merge if the
source file references a known paid-API hostname.

### Any new external network call (whole-repo, AC-2.4 extension)

Beyond Source Adapters, **every** PR that introduces a new external
network call — Telegram, GitHub Pages, the Claude CLI, a future
publishing target, anything — must declare in the PR body:

- [ ] **What it calls**: hostname or service name
- [ ] **Cost impact**: confirmed zero (free tier or self-hosted),
      or document the rationale + non-zero estimate
- [ ] **Failure mode**: how the pipeline degrades when the endpoint
      is unreachable (FD R6 / NFR-003 graceful-degradation contract)

Two CI guards back this up at the source level:
- `scripts/check_no_paid_apis.py` — paid-hostname grep on
  `src/investo/sources/`.
- `scripts/check_no_anthropic_sdk.py` — repo-wide ban on the
  `anthropic` Python SDK and on `subprocess` shell-form / string-form
  invocations (NFR-002 AC-2.2 / AC-2.3 + NFR-007 AC-7.1 / AC-7.6),
  run by `tests/unit/briefing/test_no_anthropic_sdk.py`.

---

## Quality gate before commit

Every PR must pass all four:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/
uv run pytest -q
```

Test failures and lint errors block the merge — no `--no-verify`
shortcuts.

If the change touches the public site (`mkdocs.yml`, `site_docs/`,
`pyproject.toml` `[project.optional-dependencies] docs`), additionally
run the strict site build:

```bash
uv sync --extra dev --extra docs   # ensure both extras present
uv run mkdocs build --strict
```

`--strict` fails on broken links, unrecognized config, and pages not
in `nav` — same gate the `pages.yml` workflow runs. Local preview
during writing: `uv run mkdocs serve` (no `--strict`).

---

## Operator runbook (u6 infra/CI)

For day-to-day operation of the cron pipeline + manual interventions.

### First production cutover checklist

Run this once before treating the cron as live:

1. Set the five required GitHub Secrets in **Settings -> Secrets and
   variables -> Actions**.
2. Enable Pages in **Settings -> Pages -> Build and deployment ->
   Source: GitHub Actions**.
3. Trigger **Actions -> daily-briefing -> Run workflow** with
   `target_date` blank for the cron default, or an ISO date for a
   backfill.
4. Verify the resulting runs:

```bash
gh run list --repo github.com/murphyGo/investo --workflow daily-briefing.yml --limit 5
gh run list --repo github.com/murphyGo/investo --workflow pages.yml --limit 5
```

5. Confirm the public Telegram channel received the briefing and the
   Pages URL renders the same archive entry.

### GitHub Secrets (required)

The five required secrets `daily-briefing.yml` injects into `python -m investo`
must all be set in **Settings → Secrets and variables → Actions** before
the first cron fires:

| Secret | Source | Purpose |
|--------|--------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude /login` setup token | Authenticates the `claude` CLI subprocess (NFR-002 / US-009 — never a raw Anthropic API key) |
| `TELEGRAM_BOT_TOKEN` | BotFather's `/newbot` → token | Bot identity for both dispatchers |
| `TELEGRAM_BRIEFING_CHANNEL_ID` | `@your_public_channel` username or numeric ID | Public briefing channel (FR-004) |
| `TELEGRAM_OPERATOR_CHAT_ID` | Operator's 1:1 chat ID (numeric) | Operator failure alerts (FR-007) — **MUST be disjoint** from the channel above (CLAUDE.md #5; `__main__._validate_env` rejects equality, including whitespace-tolerant comparison) |
| `SITE_URL_BASE` | e.g. `https://murphygo.github.io/investo` | Public mkdocs site base URL — included in the Telegram briefing footer link |

If any are missing the workflow exits 1 with a `ConfigError` that
names the missing var(s); when `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_OPERATOR_CHAT_ID` are present the pipeline still attempts a
single best-effort operator alert before exiting (AC-007-3).
The workflow also runs a `Preflight required secrets` step immediately
before `python -m investo`; missing or empty required secrets, equal
Telegram briefing/operator chat IDs, and malformed `SITE_URL_BASE`
fail that step with GitHub Actions `::error::` annotations that name
the variable or invariant without echoing secret values.
The job installs the Claude Code CLI with
`npm install -g @anthropic-ai/claude-code` before the preflight step and
runs `claude --version`; a missing CLI binary is therefore caught before
the market-data collection/generation pipeline starts.

### GitHub Secrets (optional — per-adapter)

| Secret | Source | Effect when absent |
|--------|--------|---------------------|
| `FRED_API_KEY` | Free key from <https://fred.stlouisfed.org/docs/api/api_key.html> | The `fred-macro` adapter raises `SourceFetchError(transient=False)` on its first invocation; the aggregator catches per FD R6 and `fred-macro` contributes `[]` for the run. All other adapters (FOMC RSS, yfinance, CoinGecko) run normally. The pipeline still ships a briefing — just without macro-indicator content. |
| `OPENAI_API_KEY` | OpenAI dashboard key | **Disabled by default** — the `daily-briefing.yml` workflow forces `INVESTO_OPENAI_VISUALS=0` so the OpenAI visual surface never runs in CI even when this secret is configured. See "OpenAI visual surface (cost-bearing)" below for the override contract. |

Adapter-level optional secrets follow FD R13 — failure mode is graceful
degradation, never pipeline-fatal. Set `FRED_API_KEY` only if you want
macro coverage in the briefing.

### OpenAI visual surface (cost-bearing — opt-in only)

The `visuals/openai_image.py` surface (introduced in u23) generates
hero PNGs via the OpenAI Responses + image-generation API. This is the
**only** cost-bearing surface in the project. Because CLAUDE.md project
rule #4 is "free APIs only", the surface is disabled by default at
three layers:

1. **Workflow override**: `.github/workflows/daily-briefing.yml` pins
   `INVESTO_OPENAI_VISUALS=0` in the run-pipeline step's `env:` block,
   so the cron and `workflow_dispatch` runs never enable the surface
   regardless of repository-secret state.
2. **Runtime fail-safe**: `visuals.openai_image.load_openai_visual_config`
   only sets `enabled=True` when `INVESTO_OPENAI_VISUALS == "1"` AND
   `OPENAI_API_KEY` is non-empty. Either condition unmet → no OpenAI
   HTTP call (deterministic SVG cards remain).
3. **Boot-time fail-closed**: `__main__._validate_env` raises
   `ConfigError(missing=("OPENAI_API_KEY",))` when the flag is `"1"`
   but the key is unset, so the operator cannot accidentally enable
   the surface without the matching secret.

To **experiment** with the surface (locally or on a manual
`workflow_dispatch`):

1. Set `OPENAI_API_KEY` as a GitHub Secret (or local env var).
2. Edit `daily-briefing.yml` to flip `INVESTO_OPENAI_VISUALS: '0'` →
   `'1'` in **both** the preflight step and the run-pipeline step.
   Both must be flipped together — the preflight step's `0` → `1`
   makes the key required at preflight time so a misconfig fails
   before any cost is incurred.
3. Revert the workflow change before merging. The surface is for
   ad-hoc experiments, not steady-state operation.

The `_redact_diagnostic_text` / `sanitize_source_error_message` /
`sanitize_provenance_text` chokepoints (u27) all redact
`OPENAI_API_KEY` values from any operator-facing surface even when the
flag is `0`, so a leaked key in a fixture or stderr never reaches a
public artefact.

### Cron schedule

Two cron entries in `.github/workflows/daily-briefing.yml`:

| Cron (UTC)              | KST equivalent       | Fires for                          |
|-------------------------|----------------------|------------------------------------|
| `0 22 * * 0,1,2,3,4`    | Mon-Fri 07:00 KST    | Prior US trading session (Mon-Fri close) |
| `0 0 * * 6`             | Sat 09:00 KST        | Friday's US trading session              |

KST has been a fixed UTC+9 since 1988 (no DST), so these cron times
are stable year-round even though the prior-trading-day's market
close shifts ±1 hour twice a year via US DST.

### Manual trigger (`workflow_dispatch`)

Use **Actions → daily-briefing → Run workflow** to trigger off-cron.
The form exposes one optional input:

- **`target_date`** (ISO-8601 `YYYY-MM-DD`): override
  `resolve_target_date(now_utc)`. Useful for backfills + US-public-
  holiday recoveries (the orchestrator deliberately does NOT consult
  a US trading calendar per Q3=A; holiday days surface as
  empty-collect → operator alert; the operator re-triggers manually
  with `target_date=last-trading-day`). Leave blank for the cron-time
  default.

A typo in `target_date` is a hard error (exits 1 with a `ConfigError`
that includes the malformed value) — the pipeline will NOT silently
roll back to the cron default, because that would publish for the
wrong date entirely.

### US public holidays (Q3=A recovery flow)

When the US market is closed (Thanksgiving, July 4, Memorial Day,
etc.), the cron fires as usual but the FOMC RSS / future adapters
return zero items for that date. Result:

1. `_stage_collect` raises `EmptyCollectError`.
2. `run_pipeline` routes to `OperatorAlerter.alert(stage="collect")`
   → operator gets a Telegram alert.
3. Pipeline exits with status `FAILED` → workflow turns red + GHA's
   default email alert fires.
4. **Operator action**: re-trigger `daily-briefing` via
   `workflow_dispatch` with `target_date=<last-actual-trading-day>`
   (e.g. for Thursday 2026-11-26 Thanksgiving, use the Wednesday
   2026-11-25 close: re-trigger on Friday morning with
   `target_date=2026-11-25`).

The pipeline writes to `archive/2026/11/2026-11-25.md`, which git
already contains from the prior day's run — the **same-day overwrite
contract** (FR-006) replaces it cleanly with the re-run version.

### Pages deploy

`pages.yml` triggers automatically on every push to `main` (including
the daily-briefing bot's git pushes). The two-job split is:

1. **`build`** — checks out, installs `--extra docs`, runs
   `mkdocs build --strict`, uploads the `site/` artifact.
2. **`deploy`** — `actions/deploy-pages@v4` swaps the published site
   atomically. **A failed build preserves the previously deployed
   site** (no rollback action needed).

Before the first deploy, enable Pages in **Settings -> Pages -> Build
and deployment -> Source: GitHub Actions**. If the `Configure Pages`
step fails with `Get Pages site failed` / `HttpError: Not Found`, the
repo's Pages site is not enabled or is still configured for branch
deployment instead of GitHub Actions.

To preview the site locally during a `mkdocs.yml` or `site_docs/`
edit:

```bash
uv run mkdocs serve   # localhost:8000, hot-reload, non-strict
```

---

## Project rules (enforced)

- **No Anthropic SDK**: LLM calls go through `briefing/claude_code.py`
  via `subprocess.run(["claude", "-p", ...])`. The `anthropic` Python
  package must NOT be added to dependencies (NFR-002 / US-009).
- **No paid APIs**: zero-cost operating budget (NFR-002).
- **No live external endpoints in tests**: all adapter tests replay
  recorded fixtures via `MockTransport` (R10).
- **Module boundary**: only `orchestrator` may import `sources` /
  `briefing` / `publisher` / `notifier`. The other 4 work units may
  share only `models` and the type contracts re-exported from each
  unit's `__init__.py`.
- **Disclaimer enforcement**: every published briefing carries the
  legal disclaimer; `publisher.verify_disclaimer` blocks the publish
  on failure (NFR-004).
- **Telegram channel separation**: the public briefing channel
  (`BriefingPublisher`) and the operator 1:1 chat (`OperatorAlerter`)
  must NOT share a `chat_id` (FR-004 vs FR-007).

---

## Where to find what

| Document | Purpose |
|----------|---------|
| `docs/requirements.md` | FR/NFR + acceptance criteria (single source of truth) |
| `docs/DESIGN.md` | Architecture summary (developer-facing) |
| `docs/TECH-DEBT.md` | Technical-debt registry |
| `aidlc-docs/aidlc-state.md` | AIDLC stage / unit progress |
| `aidlc-docs/audit.md` | Append-only audit log of every stage decision |
| `aidlc-docs/construction/<unit>/` | Per-unit FD / NFR Requirements / Code summaries |
| `CLAUDE.md` | Quick orientation for AI-assisted development |
