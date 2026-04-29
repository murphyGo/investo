# Code Generation Plan: `u4 notifier`

**Date**: 2026-04-30
**Unit**: u4 notifier — Telegram dispatcher (BriefingPublisher + OperatorAlerter)
**Stage**: Code Generation (FD + NFR Requirements both SKIPPED per `execution-plan.md`)

**Plan source**:
- `aidlc-docs/inception/application-design/unit-of-work.md` — u4 module path + DoD
- `aidlc-docs/inception/application-design/component-methods.md` — canonical method signatures (C4 notifier)
- `docs/requirements.md` — FR-004 (텔레그램 채널), FR-007 (운영자 1:1), NFR-003 (graceful degradation)
- `src/investo/models/briefing.py` — `BriefingNotification` (4096-unit UTF-16 cap, already validated)
- `src/investo/models/results.py` — `SendResult`, `FailureContext`, `FailureStage` (already shipped)
- `CLAUDE.md` — project rule #5: **BriefingPublisher and OperatorAlerter must NOT share `chat_id`**

---

## Unit Context

### Stories closed by this stage
- **US-004 텔레그램 시황 채널 알림** (closes when this unit's CG completes)
- **US-007 운영자 실패 알림** (closes when this unit's CG completes)

### Dependencies
- `investo.models.BriefingNotification` — public-channel payload (already shipped + 4096 UTF-16-unit validated at construction)
- `investo.models.SendResult` — outcome value object with cross-field invariant (ok/message_id/error mutually consistent)
- `investo.models.FailureContext` — operator alert payload (with 2000-char traceback excerpt cap)
- `investo.models.FailureStage` — operator-alert routing stage taxonomy
- `investo.models.Briefing` — consumed by `summary.build_summary` to derive the public-channel summary
- `httpx` — already locked dependency (used by u1 sources); u4 uses `httpx.AsyncClient` for Telegram Bot API
- **NEW external deps**: NONE.

### Definition of Done (from unit-of-work)
- [ ] `BriefingPublisher` sends only to the public channel (channel_id separation verified)
- [ ] `OperatorAlerter` sends only to the operator chat
- [ ] Two classes do NOT share a dispatch path (constructor parameters enforce isolation)
- [ ] HTTP failures → `SendResult(ok=False, error=...)`, NEVER raise
- [ ] Body-length truncation (UTF-16 code units, NOT Python char count)
- [ ] `parse_mode` set correctly; URL preservation through truncation

### Module boundary recap
- u4 imports from `investo.models` only. NO imports from `sources / briefing / publisher / orchestrator`.
- u4 is consumed by `u5 orchestrator` exclusively. The orchestrator constructs `BriefingPublisher` + `OperatorAlerter` with disjoint chat IDs from environment variables.

### Critical project rule (CLAUDE.md #5)
> 텔레그램 채널 분리 — 공개 시황 채널(BriefingPublisher) ↔ 운영자 1:1 chat(OperatorAlerter), chat ID 공유 금지.

The two classes themselves do not assert disjointness at the unit level (each only knows its own chat_id). The orchestrator enforces at construction time. The plan adds a **u5-readiness-pin test** in Step 6 that exercises the cross-class disjoint-id invariant via constructor wiring.

---

## Steps

### Step 1: Project bootstrap

- [x] **1.1** Created `src/investo/notifier/__init__.py` — docstring describes the
  US-004 + US-007 dual-class dispatcher contract, the chat_id-separation
  invariant (CLAUDE.md #5), the non-raising failure-encoding-via-SendResult
  convention, and the bot-token redaction commitment. `__all__: list[str] = []`
  placeholder (public re-exports finalized in Step 6).
- [x] **1.2** Created `tests/unit/notifier/__init__.py` (empty) and
  `tests/unit/notifier/conftest.py` (placeholder noting per-test fixtures
  — `httpx.MockTransport` factories + `BriefingNotification` /
  `FailureContext` builders — land with the dispatcher tests in Steps 4 + 5).
- [x] **1.3** `pyproject.toml` deps confirmed unchanged. `httpx` already locked
  from u1; no new external dep.
- [x] **1.4** Quality gate: ruff ✅, ruff format ✅ (82 files), mypy --strict ✅
  (**29 source files**; +1 from u3's 28 = `notifier/__init__.py`), pytest
  **500/500** ✅ (bootstrap-only step; no new tests yet).

---

### Step 2: `_telegram.py` — internal HTTP helper

**Refs**: component-methods.md (`http: httpx.AsyncClient | None = None` injectable in BriefingPublisher + OperatorAlerter); FR-004 / FR-007 (Telegram Bot API endpoint).

- [x] **2.1** `src/investo/notifier/_telegram.py` (~125 lines):
  - `telegram_api_url(bot_token, method="sendMessage") -> str` — pure URL builder.
  - `_BOT_TOKEN_RE = re.compile(r"/bot[^/\s'\"]+")` + `_redact_bot_token(text)`
    helper — replaces every `/bot{token}` segment with `/bot[REDACTED]` so the
    URL shape stays recognizable for debugging while removing the secret.
  - `async send_message(client, *, bot_token, chat_id, text, parse_mode
    ="Markdown", disable_web_page_preview=False) -> SendResult` — non-raising
    httpx POST. Catches `httpx.TimeoutException`, `httpx.HTTPError`, non-2xx
    status, JSON-parse failures, and Telegram API `{"ok": false}`. Every error
    string is `_redact_bot_token`-sanitized before landing in `SendResult.error`.
- [x] **2.2** `tests/unit/notifier/test_telegram.py` (~210 lines, 15 tests):
  - **URL builder** (2): default + custom method.
  - **Happy path via MockTransport** (3): canonical Telegram OK response → ok=True
    with message_id; request body has expected fields (chat_id/text/parse_mode/
    disable_web_page_preview); request URL contains the bot token (correctly —
    that's how Telegram authenticates).
  - **Telegram API error** (2): `{"ok": false, "description": ...}` → ok=False
    with description in error; non-200 HTTP status → ok=False with status code.
  - **HTTP failures** (3): `TimeoutException` → ok=False; `ConnectError` →
    ok=False; invalid JSON response body → ok=False. Non-raising contract pinned.
  - **Bot-token redaction** (5): `_redact_bot_token` direct unit tests
    (single occurrence / multiple occurrences / passthrough on plain text);
    end-to-end via `send_message` for both `TimeoutException` and `ConnectError`
    where the synthetic exception message embeds the URL with token — the
    `SendResult.error` MUST NOT contain the token.
  - Quality gate: ruff ✅, ruff format ✅ (2 files reformatted on save),
    mypy --strict ✅ (30 source files; +1 from Step 1's 29 = `notifier/_telegram
    .py`), pytest **515/515** ✅ (+15 tests; 1 initial test fixed for an
    accidental httpx-private-attr usage; zero regressions in the prior 500).

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 3: `summary.py` — `build_summary` (UTF-16-aware truncation)

**Refs**: component-methods.md (`build_summary(briefing, max_chars=4096) -> str`); FR-004 (4096-unit Telegram cap COUNTED IN UTF-16 CODE UNITS — emoji = 2 units); `BriefingNotification` model already validates this on construction.

- [ ] **3.1** `src/investo/notifier/summary.py`:
  - `def build_summary(briefing: Briefing, *, site_url: str, max_units: int = 4096) -> str`
    — composes the public-channel preview text:
    ```
    📈 {target_date.isoformat()} 시황 요약

    {market_summary first ~N chars}

    상세보기: {site_url}
    ```
    Layout: emoji header + ISO date + 1-line gap + truncated `briefing.market_summary` +
    1-line gap + `상세보기: {site_url}` link footer.
  - **UTF-16 length accounting**: use `len(s.encode("utf-16-le")) // 2` to count units.
    Non-BMP chars (emoji, certain CJK) consume 2 units per code point; Python's `len`
    is by code point and would under-count. Truncation algorithm: peel chars off the
    body until the full message fits under `max_units`, append "…" (1 unit) when
    truncated. Footer URL is preserved (never truncated — site link is the whole point).
  - Return value is the SUMMARY TEXT only — `BriefingPublisher.send` wraps it in a
    `BriefingNotification(summary_text=..., site_url=..., target_date=...)` which
    re-validates the 4096 cap as a defense-in-depth.
- [ ] **3.2** `tests/unit/notifier/test_summary.py` (~10 tests):
  - **Happy path** (2): a typical Briefing → summary contains target_date ISO,
    market_summary substring, site_url. Manual UTF-16 length check stays under 4096.
  - **Korean truncation** (2): a 5000-char Korean `market_summary` → truncated body
    fits under 4096 units; "…" suffix appended; URL preserved verbatim at end.
  - **Emoji 2-unit-per-codepoint accounting** (2): a market_summary containing 2000
    📈 emojis (4000 UTF-16 units even though `len()` says 2000) → truncated to fit;
    pin the UTF-16 measurement.
  - **Trivial Briefing** (1): minimum-length `market_summary` ("요약") → summary fits
    well under cap; no truncation suffix.
  - **Footer always preserved** (1): even at the 4096-unit boundary, the
    `상세보기: {url}` footer + URL is intact.
  - **Round-trip via BriefingNotification** (1): the constructed summary, when fed
    back to `BriefingNotification(summary_text=..., site_url=..., target_date=...)`,
    passes the model's own 4096-unit validator. Belt-and-braces with the build-time
    truncation.
  - **Defense-in-depth max_units override** (1): caller can set a tighter
    `max_units=200` (e.g., for a future SMS gateway); truncation respects it.

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 4: `briefing_publisher.py` — `BriefingPublisher` class (FR-004)

**Refs**: component-methods.md C4 (`class BriefingPublisher`); FR-004 (공개 채널); chat_id-separation rule from CLAUDE.md.

- [ ] **4.1** `src/investo/notifier/briefing_publisher.py`:
  - `class BriefingPublisher`:
    - `__init__(self, *, bot_token: str, channel_id: str, http: httpx.AsyncClient |
      None = None) -> None` — kwargs-only construction (caller cannot accidentally
      swap channel_id with operator_chat_id positionally). Stores fields privately.
    - `async def send(self, payload: BriefingNotification) -> SendResult`:
      - Build full message text from `payload.summary_text` + `payload.site_url`
        (the BriefingNotification model already enforces the 4096 cap; no truncation
        here).
      - If `self._http` is None, create an `httpx.AsyncClient(timeout=30.0)` for
        the duration of the call (`async with`). Otherwise use the injected client.
      - Call `_telegram.send_message(client, bot_token=..., chat_id=self._channel_id,
        text=..., parse_mode="Markdown", disable_web_page_preview=False)`.
      - Return the `SendResult` directly — non-raising.
    - **Token never logged**: use `repr()`-safe attribute names (`_bot_token`) and
      do not include the token in any log line or `__repr__`. The default `__repr__`
      from object suffices.
  - Module-level docstring documents the FR-004 channel-isolation contract: u4 trusts
    that the orchestrator wires `channel_id` to a public-channel ID disjoint from the
    operator chat ID. The unit-level test in Step 6 pins the constructor enforcement.
- [ ] **4.2** `tests/unit/notifier/test_briefing_publisher.py` (~8 tests):
  - **Construction** (2): kwargs-only; positional args raise `TypeError`. Stored
    fields don't leak `bot_token` via `repr()` or `__repr__`.
  - **Happy path** (1, via `httpx.MockTransport`): a valid `BriefingNotification` →
    POST to `https://api.telegram.org/bot{TOKEN}/sendMessage` with JSON body
    containing `chat_id` matching channel_id + the summary text → mock returns
    `{"ok": true, "result": {"message_id": 99}}` → `SendResult(ok=True,
    message_id=99)`.
  - **HTTP failure** (1): MockTransport raises `httpx.TimeoutException` → ok=False;
    no raise.
  - **Telegram API failure** (1): mock returns `{"ok": false, "description":
    "channel not found"}` → ok=False.
  - **No raise on transport error** (1): non-raising contract pinned.
  - **Default httpx client created when http=None** (1): inspect-source style
    pin or runtime trace via mock.
  - **Channel ID is the only target** (1): MockTransport handler asserts the
    request body's `chat_id` matches the constructor's `channel_id`, NEVER any
    other value. Pins isolation at the dispatch level.

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 5: `operator_alerter.py` — `OperatorAlerter` class (FR-007)

**Refs**: component-methods.md C4 (`class OperatorAlerter`); FR-007 (운영자 1:1); same non-raising contract as BriefingPublisher.

- [ ] **5.1** `src/investo/notifier/operator_alerter.py`:
  - `class OperatorAlerter`:
    - `__init__(self, *, bot_token: str, operator_chat_id: str, http: httpx
      .AsyncClient | None = None) -> None` — kwargs-only.
    - `async def alert(self, failure: FailureContext) -> SendResult`:
      - Format the alert message from `FailureContext` fields:
        ```
        ⚠️ Pipeline failure: {stage}

        {error_type}: {error_message}

        Occurred: {occurred_at.isoformat()}

        ```{traceback_excerpt}```  (only if traceback_excerpt is not None)
        ```
        Use Markdown parse_mode; preserve the traceback in a code fence.
      - UTF-16 length: the FailureContext model already caps `traceback_excerpt`
        at 2000 chars (`_TRACEBACK_EXCERPT_MAX`), and the error_type/message are
        unbounded. The full alert MUST still fit under 4096 UTF-16 units. Use the
        same `summary._utf16_truncate` helper (extracted from Step 3) defensively.
      - Wrap the same `_telegram.send_message` call as BriefingPublisher.
  - **MUST NOT include the bot token in the alert text** even when `error_message`
    contains it accidentally. Apply the same redaction regex as Step 2 to the
    final text.
- [ ] **5.2** `tests/unit/notifier/test_operator_alerter.py` (~9 tests):
  - **Construction** (2): kwargs-only; no token leak via repr.
  - **Happy path** (1): a `FailureContext(stage="briefing", error_type="BriefingGen
    erationError", error_message="...")` → POST with `chat_id == operator_chat_id`
    + the formatted alert text → ok=True.
  - **Traceback included** (1): when `traceback_excerpt` is non-None, the alert
    text contains the excerpt inside a triple-backtick code fence.
  - **Traceback omitted gracefully** (1): when `None`, the alert text does NOT
    contain stray triple-backticks.
  - **HTTP failure** (1): non-raising; `SendResult.ok=False`.
  - **Bot-token redaction in error_message** (1): a `FailureContext` whose
    `error_message` accidentally embeds the bot token → final alert text does NOT
    contain the token. Critical NFR-007 safety.
  - **Long error_message truncated** (1): a 10000-char `error_message` → final
    alert fits under 4096 UTF-16 units; truncation indicator present.
  - **Operator chat ID is the only target** (1): MockTransport handler asserts
    `chat_id` is `operator_chat_id`, never the briefing channel.

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 6: `notifier/__init__.py` public surface + chat_id-separation pin

- [ ] **6.1** Finalize `src/investo/notifier/__init__.py`:
  - Re-export `BriefingPublisher`, `OperatorAlerter`, `build_summary`. Internal helpers
    (`_telegram`) stay private.
  - Module docstring documents the orchestrator wiring contract (disjoint chat IDs
    from environment variables) and the non-raising failure-encoding-via-SendResult
    convention.
- [ ] **6.2** `tests/integration/test_notifier_smoke.py` (~80 lines, 3 tests):
  - **End-to-end public dispatch** (1): construct `BriefingPublisher` + valid
    `BriefingNotification` → MockTransport handler captures the request →
    asserts URL + chat_id + body shape; ok=True returned.
  - **End-to-end operator dispatch** (1): construct `OperatorAlerter` + valid
    `FailureContext` → MockTransport captures → asserts chat_id is the operator's
    + alert text contains stage + error context.
  - **Chat-ID separation invariant** (1): construct BOTH classes from the same
    bot_token but DISJOINT chat_ids. Run send + alert against the same MockTransport
    handler and assert each request's chat_id matches its respective class's
    constructor parameter — NEVER cross-pollinated. Pins the CLAUDE.md #5 rule
    at the dispatch level. (The orchestrator-side assertion that the IDs are
    actually disjoint is u5's responsibility; this test pins the *if* the ids
    ARE disjoint, the dispatch respects that.)
- [ ] **6.3** Public-surface pin: `from investo.notifier import BriefingPublisher,
  OperatorAlerter, build_summary` resolves; folded into the integration smoke
  (single home; matches u3's Step 7.3 consolidation precedent).

**Quality gate**: ruff, ruff format, mypy --strict, pytest.

---

### Step 7: Sub-agent code review

Delegate fresh-eyes review per dev-investo skill §5.1. Focus areas:

- **Bot-token redaction**: is the regex robust against URL-embedded tokens in httpx
  error messages? What about non-URL contexts (e.g., raw repr of a Request object)?
- **UTF-16 truncation correctness**: `len(s.encode("utf-16-le")) // 2` — is this
  the correct count? What about surrogate pairs that get split mid-character?
- **`httpx.AsyncClient` lifecycle**: when `http=None`, the publisher creates a
  client per call (`async with`). Is that wasteful for a single-pipeline run?
  Should the orchestrator inject a shared client? Document.
- **Markdown parse_mode safety**: a `Briefing.market_summary` containing
  Markdown special chars (`*`, `_`, `[`, etc.) might break parse_mode rendering
  or trigger Telegram's parser-error response. Should the summary be sanitized?
- **Module boundary**: u4 imports only `investo.models` + `httpx` (allowed) +
  stdlib. NO imports from other 4 work units.
- **Failure-mode coverage**: every public method has a documented exception path
  with a test pin (or non-raising contract verified).
- **Chat_id separation**: is the unit-level pin (Step 6.2 third test) sufficient?
  Should we also add an orchestrator-readiness assertion (e.g., a function
  `assert_disjoint_chat_ids(briefing_publisher, operator_alerter)` that u5 calls)?

After review:
- Apply Critical / High fixes before commit.
- Triage Medium / Low into TECH-DEBT or apply.

---

### Step 8: Closeout summary.md + final quality gate

- [ ] **8.1** `aidlc-docs/construction/u4-notifier/code/summary.md`:
  - Files-created table (source + tests).
  - FR-004 / FR-007 / NFR-003 traceability table.
  - Story status: US-004 ✅ closed, US-007 ✅ closed.
  - Open TECH-DEBT (any new from u4; carry forward DEBT-001 to DEBT-013 from prior).
  - Hand-off notes for u5 orchestrator: stable surface = `BriefingPublisher`,
    `OperatorAlerter`, `build_summary`; u5 wires the env-var-derived chat_ids and
    enforces disjointness at construction time.
- [ ] **8.2** Final quality gate: ruff ✅, ruff format ✅, mypy --strict ✅
  (~32 source files: 28 prior + 4 new u4), pytest ✅ (~500 + ~50 u4 = ~550 tests).

**Exit**: ✅ `u4 notifier` Code Generation stage CLOSED. Stories US-004 + US-007 close.
The unit is eligible for `/cross-check`. Next: `u5 orchestrator` (the integration
glue), then `u6 infra/CI` (YAML/config only), then global Build & Test.

---

## Step Dependency Graph

```
1 bootstrap
  ├── 2 _telegram   (httpx HTTP helper)
  ├── 3 summary     (build_summary; depends on Briefing model only)
  ├── 4 briefing_publisher  (depends on 2 + BriefingNotification model)
  ├── 5 operator_alerter    (depends on 2 + FailureContext model + summary helper)
  ├── 6 __init__ + smoke    (depends on 4, 5, summary)
  ├── 7 review              (depends on all)
  └── 8 closeout            (depends on all)
```

In practice: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 sequentially.

---

## Estimated Scope

- ~5 source files in `src/investo/notifier/` (`__init__.py`, `_telegram.py`,
  `summary.py`, `briefing_publisher.py`, `operator_alerter.py`)
- ~6 test files in `tests/unit/notifier/` + 1 integration smoke
- ~8 plan steps, each yielding 1 commit
- Solo dev: ~1 day (similar size to u3)

---

## How to Approve

This plan is the single source of truth for `u4` Code Generation. Reply
**approve** to begin Step 1; **changes [N]** to revise step N.
