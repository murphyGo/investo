# Code Generation Plan: `u80 notifier-decomposition-and-dispatcher-base`

**Date**: 2026-05-28
**Unit**: u80 notifier-decomposition-and-dispatcher-base
**Stage**: Code Generation (refactor)
**Status**: Planned — not started (0/4 steps)
**Source**: 2026-05-28 abstraction review — `notifier/`
**Estimated Effort**: ~3-4 h
**Dependencies**: **u79** (UTF-16 helpers must already live in `_internal/text.py`)
**Wave**: 14 — read `wave-14-abstraction-refactor-overview.md` first; its Refactor Contract governs this unit.

---

## Problem Statement

Two abstraction smells in `notifier/`:

1. **`summary.py` (755 lines) tangles data extraction with Telegram formatting.** `build_segmented_summary` (~L180-296) orchestrates ~25 helpers that mix three concerns: (a) **extraction** — pull conclusion / coverage / market-snapshot / watchlist from a `Briefing` (`_one_line_summary` ~L504-539, `_market_snapshot_line` ~L375-389, `_coverage_label` ~L496-502); (b) **formatting** — UTF-16-bounded, markdown-cleaned, price-decorated Telegram strings (`_format_pct`, `_format_compact_price`, `_decorate_watchlist_with_prices` ~L632-673); (c) **event detection** (`_imminent_event_tag` ~L672-734). Extraction and presentation cannot be tested independently.
2. **`BriefingPublisher` and `OperatorAlerter` duplicate the markdown-fallback dispatch.** Both define `_is_markdown_parse_error` (`briefing_publisher.py:30`, `operator_alerter.py:35`) and both implement the same "try `parse_mode=Markdown`, on parse error retry with `parse_mode=None`" loop (`briefing_publisher.py:90-108` vs `operator_alerter.py:131-149`), with near-identical `__init__` (bot_token, chat/channel id, optional http, dry_run, 30s timeout).

---

## Goal

- Split `summary.py` into an **extraction** layer (returns plain data) and a **formatting** layer (renders Telegram-safe strings), so each is independently testable.
- Introduce a `TelegramDispatcher` base that owns the shared markdown→plain fallback; both clients inherit it. `_is_markdown_parse_error` lives in one place.

Identical Telegram message bytes for every fixture — this is the proof.

---

## Existing Coverage / Deduplication

- UTF-16 truncation now comes from `_internal/text.py` (delivered in u79) — the formatter imports it; do not re-add local copies.
- `_telegram.py::send_message` already encapsulates the raw HTTP send + retry-budget integration — the dispatcher base **wraps** it, it does not replace it.
- **Channel separation (R5) is load-bearing:** the base must keep each instance's own `chat_id`/`channel_id`. The base must NOT introduce any shared/default chat id. `BriefingPublisher` → public channel; `OperatorAlerter` → operator chat; never the same value. Keep the existing test that pins channel separation green.

---

## Scope Boundary

In scope:
- `notifier/_summary_extract.py` (extraction) + keep formatting in `summary.py` (or `_summary_format.py`); `build_segmented_summary` becomes a thin compose of the two.
- `notifier/_dispatcher.py::TelegramDispatcher` base; both clients subclass it.

Out of scope:
- Changing summary content, ordering, truncation limits, or event-tag wording.
- Changing `_telegram.py` HTTP/retry behavior.
- Webhooks / severity-debounce modules (not part of this smell).

---

## Stage Decision

- **Functional Design — SKIP.** Internal restructuring of notifier; no new entity.
- **NFR Requirements — SKIP.** No new dependency/service/secret/cost. Channel-separation and R13 NFRs are preserved, not changed.

---

## Implementation Steps

### Step 1 — extract the summary data layer `[ ]`
- [ ] Create `notifier/_summary_extract.py` with pure functions that take a `Briefing` (+ optional watchlist prices) and return structured data: conclusion line, coverage label, market snapshot values, watchlist terms, imminent-event info. No Telegram formatting, no UTF-16, no markdown in this module.
- [ ] Keep markdown-cleaning + UTF-16 truncation + price decoration in the formatting layer (`summary.py` or new `_summary_format.py`), importing UTF-16 from `_internal/text.py`.
- [ ] **Decide where event detection lives (review 2026-05-28):** the problem statement names THREE concerns (extraction / formatting / event detection `_imminent_event_tag`). "Imminent event" is a what-counts-as-imminent policy — arguably its own reason to change. Either give it its own `_events.py`, or add one sentence justifying why it shares the extraction module's change-axis. Do not silently fold it in unexamined.
- **Acceptance**: `build_segmented_summary` produces byte-identical output; `tests/unit/notifier/test_summary.py` passes unchanged; event-detection home is explicitly decided.

### Step 2 — shared dispatch (composition over inheritance) `[ ]`
> **Frame this as a shared helper/mixin, NOT a Liskov base class (review 2026-05-28, guide §3 LSP).** The two clients are NOT substitutable through a common supertype — `BriefingPublisher.send(BriefingNotification)` and `OperatorAlerter.alert(FailureContext)` have distinct public surfaces; nobody holds a `TelegramDispatcher` and calls a polymorphic method. So this is code-reuse, not an is-a hierarchy. Prefer a shared `dispatch(...)` free function (or injected collaborator) both clients call, over a base class — this also structurally prevents a shared/default `chat_id` field on a base (protecting R5). If a class is used, name/document it as a reuse mixin, and claim only the dedup benefit (AC-80.2), not a polymorphism/OCP benefit it doesn't deliver.
- [ ] Create the shared dispatch in `notifier/_dispatcher.py`: an async `dispatch(*, bot_token, chat_id, http, dry_run, text, **send_kwargs)` that tries `parse_mode="Markdown"`, and on `_is_markdown_parse_error` retries with `parse_mode=None`. Move `_is_markdown_parse_error` here as the single definition. **`dispatch` OWNS `parse_mode` exclusively** — exclude `parse_mode` from the `**send_kwargs` passthrough (assert/document it must not be passed) so a caller cannot re-leak or override the markdown→plain quirk (review 2026-05-28, guide §9.4 minimize-leak-surface).
- [ ] `BriefingPublisher.send(...)` and `OperatorAlerter.alert(...)` call the shared `dispatch(...)`, each passing its own chat/channel id. No shared/default id anywhere.
- **Acceptance**: `test_telegram.py` and operator-alerter tests pass unchanged; the markdown-fallback path is pinned in the dispatcher's own test; a test asserts `parse_mode` cannot be injected via `send_kwargs`.

### Step 3 — channel-separation + dry-run verification `[ ]`
- [ ] Confirm the two clients still cannot share a chat id (existing R5 test green; add one to the base if missing).
- [ ] Confirm dry-run gate and 30s timeout defaults are preserved for both.
- **Acceptance**: channel-separation test green; dry-run test green.

### Step 4 — full gate `[ ]`
- [ ] ruff / ruff-format / mypy --strict / pytest / mkdocs build --strict.
- **Acceptance**: full gate green.

---

## Acceptance Criteria

- **AC-80.1** — `summary.py` extraction and formatting are separate modules; `build_segmented_summary` output is byte-identical to pre-refactor.
- **AC-80.2** — `_is_markdown_parse_error` and the markdown→plain fallback exist once, in `TelegramDispatcher`; both clients inherit it.
- **AC-80.3** — Channel separation (R5) preserved and tested; the base introduces no shared/default chat id.
- **AC-80.4** — Every pre-existing notifier test passes unchanged; mypy --strict clean.

---

## Tests / Validation

- `tests/unit/notifier/test_summary.py`, `test_telegram.py`, operator-alerter + briefing-publisher tests — stay green unchanged.
- New: `tests/unit/notifier/test_dispatcher.py` (markdown fallback + channel separation), `test_summary_extract.py` (extraction data only).
- Gate: targeted notifier pytest; full gate before closeout.

---

## Non-Goals

- Changing any summary wording, ordering, or truncation limit.
- Touching `_telegram.py` transport, webhooks, or severity-debounce.
