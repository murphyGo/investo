# u4 notifier — Code Generation Summary

**Date**: 2026-04-30
**Stage**: Code Generation (final stage for u4 notifier; FD + NFR Requirements both SKIP per execution-plan)
**Status**: ✅ COMPLETE
**Stories closed**: US-004 (텔레그램 시황 채널 알림), US-007 (운영자 실패 알림)

---

## Files created

### Source code (`src/investo/notifier/`)

| File | LOC | Role |
|------|----:|------|
| `__init__.py` | 51 | Public surface — 3 re-exports + module docstring; documents kwargs-only ctor anti-swap design + shared-client production tip (Steps 1, 6, 7) |
| `_telegram.py` | 133 | Internal HTTP helper — `telegram_api_url`, `send_message` (non-raising), two-layer bot-token redaction `_redact_bot_token` (URL form + shape form, NFR-007) (Steps 2, 7) |
| `summary.py` | 109 | UTF-16-aware `build_summary` — surrogate-pair-safe `_utf16_truncate`, `DEFAULT_MAX_UNITS=4096`, footer URL preservation (Step 3) |
| `briefing_publisher.py` | 81 | `BriefingPublisher` class — kwargs-only ctor (anti-swap), `async send`, optional shared `httpx.AsyncClient` injection (Step 4) |
| `operator_alerter.py` | 105 | `OperatorAlerter` class — kwargs-only ctor, `async alert`, `_format_alert_text` w/ optional traceback fence, defense-in-depth redaction + UTF-16 truncation (Step 5) |
| **Total** | **479** | 5 source files |

### Tests (`tests/unit/notifier/` + `tests/integration/`)

| File | LOC | Tests | Role |
|------|----:|------:|------|
| `__init__.py` | 0 | 0 | Empty marker (Step 1) |
| `conftest.py` | 7 | 0 | Placeholder docstring (Step 1; future home for shared `_mock_client` per DEBT-016) |
| `test_telegram.py` | 279 | 17 | URL builder + happy + Telegram-API-error + transport-error + redaction (URL form, shape form, false-positive guard) (Steps 2, 7) |
| `test_summary.py` | 230 | 17 | UTF-16 helpers + happy + truncation (Korean / emoji / lone-high-surrogate) + footer preservation + round-trip via `BriefingNotification` validator (Steps 3, 7) |
| `test_briefing_publisher.py` | 185 | 8 | Construction (anti-swap, repr) + happy (3 via MockTransport) + failure (2) + default-client lifecycle (Step 4) |
| `test_operator_alerter.py` | 254 | 10 | Construction (2) + happy (2) + traceback handling (2) + failure (1) + redaction (1) + UTF-16 truncation defense (1) + public surface (1) (Step 5) |
| `tests/integration/test_notifier_smoke.py` | 172 | 4 | End-to-end public dispatch + operator dispatch + chat_id-separation invariant + public-surface importability (Step 6) |
| **Total** | **1,127** | **56** | 6 test files (5 unit + 1 integration) |

### Surface area

| Public re-export | Defined in | Consumed by |
|------------------|------------|-------------|
| `BriefingPublisher` | `briefing_publisher.py` | u5 orchestrator (constructed with `TELEGRAM_BRIEFING_CHANNEL_ID`) |
| `OperatorAlerter` | `operator_alerter.py` | u5 orchestrator (constructed with `TELEGRAM_OPERATOR_CHAT_ID`) |
| `build_summary(briefing, *, site_url, max_units=4096)` | `summary.py` | u5 orchestrator (composes the public-channel preview text from `Briefing` + site URL) |

The internal HTTP helper `_telegram` (`telegram_api_url`, `send_message`, `_redact_bot_token`) is intentionally NOT re-exported — implementation detail, may evolve without breaking u5.

### Cross-unit imports (module-boundary)

u4 imports ONLY from:
- `investo.models` (re-exported from `investo.models.briefing` + `investo.models.results`) — `Briefing`, `BriefingNotification`, `SendResult`, `FailureContext`, `FailureStage` are the consumed shapes.

u4 does NOT import from `sources / briefing / publisher / orchestrator`. Verified by `grep -rn "from investo" src/investo/notifier/` (only `investo.models` + intra-`investo.notifier.*`).

---

## FR / NFR traceability

| AC | Description | Pinned by |
|----|-------------|-----------|
| FR-004 텔레그램 시황 채널 | `BriefingPublisher.send(payload)` POSTs to public channel via Bot API `sendMessage` | `test_briefing_publisher.py::test_send_request_chat_id_matches_channel_id` + integration smoke `test_briefing_publisher_end_to_end` |
| FR-004 4096-unit cap | `build_summary` returns ≤ 4096 UTF-16 units; `BriefingNotification` model double-validates | `test_summary.py::test_build_summary_fits_under_default_max_units` + `::test_build_summary_round_trip_through_briefing_notification` |
| FR-004 site URL footer | Truncation preserves trailing `상세보기: {url}` line | `test_summary.py::test_build_summary_footer_url_always_preserved_at_truncation` |
| FR-007 운영자 1:1 chat | `OperatorAlerter.alert(failure)` POSTs to operator chat via Bot API `sendMessage` | `test_operator_alerter.py::test_alert_chat_id_matches_operator_chat_id` + integration smoke `test_operator_alerter_end_to_end` |
| FR-007 alert text shape | `_format_alert_text(failure)` → ⚠️ header + `error_type: error_message` + `Occurred: ISO` + optional triple-backtick traceback fence | `test_operator_alerter.py::test_alert_text_contains_failure_stage_and_error_message` + `::test_alert_text_includes_traceback_when_present` |
| NFR-003 graceful degradation | All HTTP failures (timeout, connect, non-200, Telegram `ok: false`, invalid JSON) → `SendResult(ok=False, error=...)`, NEVER raise | `test_telegram.py::test_send_message_handles_*` (5 tests covering each transport+API failure mode) + `test_briefing_publisher.py::test_send_returns_failure_on_connect_error` + `test_operator_alerter.py::test_alert_returns_failure_on_connect_error` |
| NFR-007 bot-token redaction | `_redact_bot_token(text)` strips `https://api.telegram.org/bot{TOKEN}/...` AND bare-shape `bot<digits>:<≥20 alphanumeric/underscore/dash>` from any string emitted in `SendResult.error` | `test_telegram.py::test_redact_bot_token_*` (6 tests covering URL form, shape form, multi-occurrence, no-false-positive on `botany`/`bot123:short`, redaction in timeout error, redaction in HTTP error) |
| NFR-007 redaction defense-in-depth in alerts | `OperatorAlerter.alert` re-redacts `failure.error_message` before formatting (covers upstream `FailureContext` constructed from poorly-sanitized logs) | `test_operator_alerter.py::test_alert_redacts_bot_token_in_error_message` |
| CLAUDE.md #5 dispatch isolation | `BriefingPublisher` and `OperatorAlerter` use kwargs-only ctors; their `chat_id`s are independent constructor args. The orchestrator wires disjoint env-var-derived IDs. | `test_briefing_publisher.py::test_construction_requires_kwargs` + `test_operator_alerter.py::test_construction_requires_kwargs` + integration smoke `test_chat_id_separation_invariant` (cross-class swap detector) |
| UTF-16 surrogate-pair safety | Truncating mid-surrogate-pair drops the orphan high half (result is valid UTF-16) | `test_summary.py::test_utf16_truncate_drops_partial_surrogate_pair` + `::test_utf16_truncate_drops_lone_high_surrogate_at_position_zero` |

u4 has no NFR Requirements file (skipped per execution-plan); the AC table above is a synthesis of FR-004 / FR-007 / NFR-003 / NFR-007 plus the CLAUDE.md #5 chat-ID-separation invariant.

---

## Open TECH-DEBT items

### From u4 (new this stage)

| ID | Priority | Source step | Description |
|----|----------|-------------|-------------|
| DEBT-014 | Low | Step 7 review | `BriefingPublisher` / `OperatorAlerter` use `parse_mode="Markdown"` without escape fallback — Telegram parse-errors degrade to `SendResult(ok=False)`; orchestrator's operator-alert path covers visibility, but worth tracking for a future `parse_mode=None` retry |
| DEBT-015 | Low | Step 7 review | `_TrackingClient` test pattern fragile to httpx version changes — works today; only matters at httpx upgrade |
| DEBT-016 | Low | Step 7 review | `_mock_client` test helper duplicated across 3 u4 test files (sibling-shape with DEBT-010 / DEBT-013); `conftest.py` is the destination |

### Cross-unit / pre-existing (unchanged)

| ID | Priority | Origin |
|----|----------|--------|
| DEBT-001 / DEBT-002 | Medium | models (briefing model invariants + date sanity bounds) |
| DEBT-007 | Medium | u2 briefing |
| DEBT-012 | Medium | u3 publisher (`_truncate_stderr` duplication w/ u2) |
| DEBT-006 / DEBT-008 / DEBT-010 / DEBT-011 | Low | u2 briefing |
| DEBT-013 | Low | u3 publisher |
| DEBT-003 / DEBT-004 / DEBT-005 / DEBT-009 | Low | u1 sources |

None block u4. 3 of 16 open items originated in u4; 5 from u2; 2 from u3; 4 from u1; 2 cross-unit (models). All u4 items are Low priority.

---

## FD-vs-implementation divergences (ratified in audit log)

Three structural deviations or ratified fixes landed during u4:

1. **Step 6.3 consolidation** — public-surface importability test. Plan called for a separate `tests/unit/notifier/test_public_surface.py`. Folded into the integration smoke's `test_public_surface_is_importable` for single-home consistency (matches u3 Step 7.3 precedent). The combined smoke now covers all 4 cross-class invariants in one file.

2. **Step 7 M1 fix — bot-token redaction extended to shape regex**. Sub-agent code review caught a real NFR-007 leak risk: the original `_BOT_TOKEN_RE = re.compile(r"/bot[^/\s'\"]+")` required a `/bot` URL prefix and missed bare-shape leaks like `"used token bot{TOKEN}"`. Fixed via two-layer redaction:
   - `_BOT_TOKEN_URL_RE` runs first → `/bot[REDACTED]` (preserves debug-friendly URL shape).
   - `_BOT_TOKEN_SHAPE_RE = re.compile(r"\bbot\d+:[A-Za-z0-9_-]{20,}")` runs second → `bot[REDACTED]` (catches anything missed; ≥20-char tail avoids false-positives on `botany`, `bot123:short`).
   3 regression tests pin: bare-token redaction works; `botany` / `bot123:short` are NOT matched; lone high surrogate at position 0 returns `""` (Q2 follow-up).

3. **Step 7 L4 doc — shared-client production tip**. Sub-agent flagged that `http=None` constructs a fresh `httpx.AsyncClient` (and a fresh TLS handshake) per call — wasteful for a real pipeline run. Added "Production tip for u5 orchestrator" section to `notifier/__init__.py` docstring recommending `http=` injection of a shared client across both classes. The unit-level default stays `http=None` (good for tests + one-shot use); u5 does the optimization.

All three ratified in `aidlc-docs/audit.md`. No cross-unit contract was broken.

---

## Story status

- ✅ **US-004** (텔레그램 시황 채널 알림) — closed by `BriefingPublisher.send(payload)` over Bot API `sendMessage` to the public channel. UTF-16-aware `build_summary` + `BriefingNotification` model double-validate the 4096-unit cap. Site URL preserved through truncation. Non-raising contract: HTTP failures encoded in `SendResult(ok=False)`.
- ✅ **US-007** (운영자 실패 알림) — closed by `OperatorAlerter.alert(failure)` over Bot API `sendMessage` to the operator 1:1 chat. Alert text formatted with stage / error type / message / timestamp / optional traceback fence. Defense-in-depth bot-token redaction + UTF-16 truncation. Disjoint from public channel by orchestrator-enforced env-var separation (CLAUDE.md #5).

---

## Pre-flight notes for u5 orchestrator

`u5 orchestrator` is the next unit. It will consume the following stable surface from `investo.notifier`:

| Symbol | Defined in | What u5 needs it for |
|--------|------------|----------------------|
| `BriefingPublisher` | `notifier.briefing_publisher` | Constructed with `bot_token=$TELEGRAM_BOT_TOKEN`, `channel_id=$TELEGRAM_BRIEFING_CHANNEL_ID`, optional `http=shared_client`. Called once per pipeline run after publisher writes the markdown. |
| `OperatorAlerter` | `notifier.operator_alerter` | Constructed with `bot_token=$TELEGRAM_BOT_TOKEN`, `operator_chat_id=$TELEGRAM_OPERATOR_CHAT_ID`, same shared client. Called from any stage's failure path with a `FailureContext`. |
| `build_summary(briefing, *, site_url)` | `notifier.summary` | Composes the public-channel preview text from a `Briefing` + the site URL (e.g., the GitHub Pages URL for the day's archived markdown). |

### What u5 must enforce (CLAUDE.md #5)

The two dispatcher classes do NOT enforce chat-ID disjointness at the unit level — each only knows its own ID. **u5 orchestrator MUST enforce at construction time** by reading `TELEGRAM_BRIEFING_CHANNEL_ID` and `TELEGRAM_OPERATOR_CHAT_ID` from disjoint env-vars and asserting they differ before constructing the dispatchers. Recommended: a small helper `assert_disjoint_chat_ids(channel_id, operator_chat_id)` that raises a config error if equal. The unit-level smoke test (`test_chat_id_separation_invariant`) verifies the dispatch routes don't cross when given disjoint IDs — it is NOT a substitute for the orchestrator's pre-construction check.

### Production tip — shared httpx.AsyncClient

To avoid a fresh TLS handshake per call, u5 should construct ONE `httpx.AsyncClient` at orchestrator startup and inject it into both dispatchers via the `http=` parameter. Pseudo-code:

```python
async with httpx.AsyncClient(timeout=30.0) as client:
    publisher = BriefingPublisher(bot_token=token, channel_id=public, http=client)
    alerter = OperatorAlerter(bot_token=token, operator_chat_id=ops, http=client)
    # ... run pipeline; on success → publisher.send; on failure → alerter.alert
```

The `http=None` default is for tests + one-shot scripts only. Documented in `notifier/__init__.py` (Step 7 L4 fix).

### Failure paths u5 routes via OperatorAlerter

u5 catches the following at the orchestrator boundary and feeds them to `OperatorAlerter.alert(FailureContext(...))`:
- `BriefingGenerationError` (from u2 — synthesis / classification / parse / budget exceeded)
- `PublisherDisclaimerError` / `PublisherIOError` / `PublisherGitError` (from u3 — pre-publish or git lifecycle failures)
- Any source-fetch error from u1 (already wrapped at the aggregator boundary; u5 surfaces aggregator's stage-tagged failures)

Each error's `last_stderr` field (where present) is already 1024-byte UTF-8 byte-truncated at construction — u5 may interpolate directly into `FailureContext.error_message` without re-truncation. The `OperatorAlerter` then UTF-16-truncates the final alert text to ≤ 4096 units.

---

## Quality gate (final, Step 8 closeout)

| Tool | Result |
|------|--------|
| `ruff check .` | ✅ |
| `ruff format --check .` | ✅ (89 files) |
| `mypy --strict src/` | ✅ (33 source files: 7 models + 8 sources + 7 briefing + 6 publisher + 5 notifier) |
| `pytest` | ✅ **556/556** passing (252 u1+models baseline + 178 u2 briefing + 70 u3 publisher + 56 u4 notifier = 556 total) |

Test breakdown for u4: 17 telegram + 17 summary + 8 briefing_publisher + 10 operator_alerter + 4 integration smoke = **56 tests**.

---

## Next stage gate

`u4 notifier` Code Generation is now CLOSED. The unit becomes eligible for `/cross-check` against requirements. Two stage gates remain for the project:

1. `u5 orchestrator` Code Generation (the integration glue — wires u1 → u2 → u3 → u4; FD/NFR per `aidlc-docs/inception/plans/execution-plan.md`)
2. `u6 infra/CI` (YAML/config only — Code Generation but no FD/NFR)

Then global `Build and Test` after every unit's CG completes.
