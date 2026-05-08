# Code Generation Plan: `u39 boot-alert-dispatch`

**Date**: 2026-05-09
**Unit**: u39 boot-alert-dispatch
**Stage**: Code Generation
**Status**: ✅ Complete
**Source**: 10-persona evaluation 2026-05-09 — persona #8 (운영자 / 1-person SRE)
**Estimated Effort**: ~1.5-2 h
**Dependencies**:
- Builds on `u31 operations-resilience` (`orchestrator/boot_alert_dedup.py` + `OperatorAlerter` + `_attempt_boot_alert` already exist).
- No new model / source change.

---

## Goal

Reconnect the broken dispatch path between `__main__._validate_env` config-error failures and the operator Telegram chat. Today, when `INVESTO_TELEGRAM_BOT_TOKEN` is missing, malformed, or the chat-id env vars are wrong, the pipeline raises a `ConfigError` and exits silently — the operator only finds out hours later that no briefing was published. The pieces needed (`boot_alert_dedup.py` 14-day ledger, `OperatorAlerter`, `_attempt_boot_alert` builder) all exist; what is missing is the actual call from the boot-time error handler in `__main__` to `_attempt_boot_alert`. This unit closes that loop.

---

## Persona evidence

> Persona #8 (운영자, P1): "어제 텔레그램 토큰 만료된 걸 오늘 아침 사이트 보고 알았다. config 오류면 그 자체가 가장 높은 우선순위 알림이어야 하는데 silent fail 이라 사실상 모니터링이 안 된다."

> Persona #8 (continued): "이미 `boot_alert_dedup` 로 14일 dedup 도 만들어 놨던데 왜 실제 호출이 안 되는지 모르겠다. 코드 베이스 어딘가에서 끊겨 있는 듯."

The persona's diagnosis is correct: u31 landed the dedup ledger and the `OperatorAlerter` retry path but did not wire the dispatch call from `__main__`'s boot-error handler. The fix is purely a wiring change — no new infrastructure, no new env var, no new fixture.

---

## Definition of Done

- [x] When `__main__._validate_env` raises `ConfigError` (or the equivalent boot-time validation error), the error path invokes `_attempt_boot_alert(error)` before the process exits with non-zero. The alert is delivered to the operator Telegram chat (not the public briefing channel) and is suppressed by the existing 14-day dedup ledger if the same fingerprint has fired in the trailing 14 days.
- [x] When `OperatorAlerter` itself fails (e.g., the bot token is the *cause* of the boot-time error), the alert attempt logs at WARNING + records nothing in the dedup ledger so a subsequent run with a fixed token still alerts. The process still exits non-zero.
- [x] `_attempt_boot_alert` rendering format matches the operator-chat conventions established in u31: Korean Markdown, header `🚨 Investo 부팅 실패`, body lines (error type, redacted message, suggested action), trailer with the run timestamp.
- [x] Redaction: the boot-error message passes through `_internal/redaction.py` STRICT policy (introduced in u27) before being serialized to the alert body, so secret-shaped tokens / chat IDs from the environment never leak into the alert payload.
- [x] Module boundary preserved: `__main__` imports only `notifier.OperatorAlerter` (and the `orchestrator/boot_alert_dedup.py` ledger helper, which lives in `orchestrator/` per existing layout). `__main__` does **not** import from `briefing/`, `publisher/`, or `sources/` — the boot-error path stays tight.
- [x] Anti-regression: a regression test exercising the missing-token scenario (set `INVESTO_TELEGRAM_BOT_TOKEN=""` in a test env, invoke `__main__.main()`, mock `OperatorAlerter.send_alert`, assert `send_alert` was called once with the expected fingerprint).
- [x] Anti-regression: dedup test — fire the same boot-error twice in the same test run, assert `OperatorAlerter.send_alert` is called exactly once (second call suppressed by the 14-day ledger).
- [x] Anti-regression: alert-failure-during-token-error test — when the bot token itself is the cause of the boot error and `OperatorAlerter.send_alert` raises, assert (1) WARNING log line emitted, (2) nothing recorded in the dedup ledger, (3) process still exits non-zero.
- [x] Full quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅, `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Wire `_attempt_boot_alert` into `__main__` Boot-Error Handler

- [x] Locate the existing `__main__._validate_env` (or equivalent boot-validation) call site and the surrounding try / except that currently exits silently.
- [x] Inject a call to `_attempt_boot_alert(error)` in the `except ConfigError as exc:` branch (or the equivalent boot-validation error class) before the exit.
- [x] If `_attempt_boot_alert` does not yet exist as a callable in `__main__`, materialize it as a thin builder that constructs `OperatorAlerter` from env, computes the dedup fingerprint, consults the ledger, and (on miss) calls `send_alert` + records.
- [x] Files affected:
  - `src/investo/__main__.py`
  - `src/investo/orchestrator/boot_alert_dedup.py` (re-export the ledger helpers if not already importable from `__main__`)
- [x] Unit tests added at `tests/unit/orchestrator/test_main_boot_alert.py`:
  - missing-token boot error → `OperatorAlerter.send_alert` called once with the rendered body.
  - same boot error fired twice → `send_alert` called once (dedup engaged).
  - boot error different from previous → `send_alert` called (separate fingerprint).
  - `OperatorAlerter.send_alert` raises → WARNING logged, ledger untouched, exit code remains non-zero.

### Step 2 — Redaction Through STRICT Policy

- [x] Pipe the boot-error message through `_internal/redaction.py::redact_text(message, policy=STRICT)` before composing the alert body. STRICT is the chokepoint added in u27 that strips bot-token / chat-id-shaped substrings.
- [x] Files affected:
  - `src/investo/__main__.py` (rendering helper)
- [x] Unit tests added:
  - simulated boot error containing a bot-token-shaped substring → rendered alert body has the substring replaced with `[REDACTED_BOT_TOKEN]`.
  - simulated boot error containing a chat-id-shaped substring → likewise.

### Step 3 — Operator-Chat Format Alignment

- [x] Confirm the alert renderer matches u31's operator-chat conventions: Korean Markdown, header `🚨 Investo 부팅 실패`, error-type / redacted-message / suggested-action body lines, run-timestamp trailer in KST.
- [x] Files affected:
  - `src/investo/__main__.py` (or `notifier/operator_alerter.py` if a new render helper is needed)
- [x] Unit tests added:
  - rendered body contains the `🚨 Investo 부팅 실패` header.
  - rendered body contains the KST timestamp in `YYYY-MM-DD HH:MM` form.
  - rendered body never contains a token-shaped substring (anti-regression on the redaction step).

### Step 4 — Verification

- [x] Run targeted boot-alert tests + the full quality gate.
- [x] Manual network dispatch was not exercised locally; automated tests cover redaction, dedup, dispatch-failure behavior, and non-zero exit preservation.

---

## Project rule compliance

- **Anthropic SDK ban**: not applicable.
- **Module boundary**: `__main__` imports only `notifier.OperatorAlerter` and `orchestrator/boot_alert_dedup.py` (the latter is the existing u31 ledger helper). **No new imports from `briefing/`, `publisher/`, or `sources/`.**
- **R13 (secret hygiene)**: enforced via STRICT redaction policy on the alert body. Anti-regression test pins that token-shaped substrings never leak. No new env var; no `_internal/redaction.py::SECRET_ENV_VARS` change needed (the existing `INVESTO_TELEGRAM_BOT_TOKEN` is already enrolled).
- **Disclaimer enforcement**: not applicable (operator-chat surface, not public briefing).
- **Channel separation**: enforced — `OperatorAlerter` writes to the operator chat (`INVESTO_OPERATOR_CHAT_ID`), never to the public briefing channel. Anti-regression: an existing u4 / u31 test already pins `OperatorAlerter.send_alert` against the operator chat ID; this unit does not change that path.

---

## Quality gate

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅ (expect ~8-12 new tests)
- [x] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **Per-error-class alert routing** — every boot error goes to the same operator chat with the same fingerprint algorithm `(error_type, sha256(message[:1024]))`. Per-class routing is a future ops unit if persona #8 ever asks for it.
- **Webhook fan-out for boot errors** — the boot-alert path stays Telegram-only. Slack / Discord boot alerts would require importing `notifier/webhooks.py` from `__main__`, which the module boundary disallows; defer until a clear need exists.
- **Boot-alert escalation when dedup window is fresh** — once dedup suppresses an alert, no escalation runs. Persona #8 explicitly rated dedup more important than escalation ("내가 14일 안에 같은 알림 또 받기 싫다는 게 더 중요").
- **Replacing `ConfigError` with a richer error hierarchy** — this unit treats `ConfigError` as the existing chokepoint. A richer hierarchy is a separate refactor.

---

## Open questions

- None blocking. All infrastructure (`OperatorAlerter`, `boot_alert_dedup.py`, redaction chokepoint) already lives in the codebase from u27 / u31. This unit is purely a 1-line wiring fix plus the surrounding rendering / redaction polish and test coverage.
