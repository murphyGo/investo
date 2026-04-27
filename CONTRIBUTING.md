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

## PR description checklist

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

---

## Quality gate before commit

Every PR must pass all four:

```bash
ruff check .
ruff format --check .
mypy --strict src/
pytest
```

Test failures and lint errors block the merge — no `--no-verify`
shortcuts.

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
