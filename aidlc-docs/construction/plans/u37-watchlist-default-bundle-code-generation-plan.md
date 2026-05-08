# Code Generation Plan: `u37 watchlist-default-bundle`

**Date**: 2026-05-09
**Unit**: u37 watchlist-default-bundle
**Stage**: Code Generation
**Status**: ✅ Complete
**Source**: 10-persona evaluation 2026-05-09 — persona #2 (중급 적극) and persona #1 (초보 직장인)
**Estimated Effort**: ~1-2 h
**Dependencies**:
- Builds directly on `u28 watchlist-usability-foundation` (`briefing/watchlist.py:DEFAULT_CORE_ALIASES` already exists with 7 core terms — BTC / ETH / SOL + NVDA / TSLA / AAPL / MSFT / GOOGL / META / AMZN, English + Korean aliases).
- Depends on `u33 watchlist-depth` (`WatchlistConfig.scopes` + `for_segment_scope`) for the per-segment resolver path that the default bundle must remain compatible with.
- No upstream model / source change; surface change only inside `briefing/watchlist.py` and its loader.

---

## Goal

Eliminate the Day-1 zero-value experience for users who have not yet authored a `watchlist.json`: when no watchlist config is detected anywhere on disk (or the `INVESTO_WATCHLIST_CONFIG` env var is unset / blank / points to a non-existent file), the briefing pipeline must auto-activate the existing `DEFAULT_CORE_ALIASES` bundle so the ⑤ "주요 종목" section renders at least one matched callout in every segment that has any covered candidate items. The bundle is never serialized to disk; the on-disk config remains the single source of truth when present and is unaffected.

---

## Persona evidence

> Persona #2 (중급 적극, P2): "watchlist 가 처음에 비어 있어서 ⑤ 주요 종목이 항상 빈 슬롯 콜아웃으로 시작된다. 메이저 종목 정도는 기본으로 잡혀 있어야 첫날부터 'investo 가 내 종목을 보고 있다'는 인상을 받는다."

> Persona #1 (초보 직장인, P1): "config 파일을 만들어야 한다는 사실 자체를 모름. 첫 발행에 NVDA / TSLA / BTC 가 자동으로 잡혀야 비로소 '아, 이게 내가 들어본 종목들 얘기를 해 주는구나' 가 된다."

Both quotes converge on the same defect: **`DEFAULT_CORE_ALIASES` already exists in code but is never the active default at the loader call-site** — the resolver currently returns an `is_empty()=True` config when no file is discovered, so the per-segment matcher always emits the empty branch and the ⑤ section degrades to the COVERAGE_HOLD / UNCONFIGURED placeholder. The fix is a single resolver change: empty / missing config → `WatchlistConfig.from_default_bundle()` instead of `WatchlistConfig.empty()`.

---

## Definition of Done

- [x] `briefing/watchlist.py::load_watchlist_config(...)` returns a `WatchlistConfig` populated from `DEFAULT_CORE_ALIASES` whenever the on-disk path is missing, the file is unreadable, the JSON is empty, or the `INVESTO_WATCHLIST_CONFIG` env var is unset / blank / points to a non-existent file. Verified end-to-end by running `investo briefing run --segment domestic-equity` (or equivalent dev entry) with no `watchlist.json` present and confirming the archive markdown's ⑤ section renders at least one match for any segment whose candidate pool contains a default-bundle alias.
- [x] When a real on-disk config is present *and* parses, the default bundle is **not** layered onto it (the on-disk file remains the single source of truth — the user's authored exclusion of NVDA must be honoured even if NVDA is in the default bundle). Verified by a regression test that loads a config containing only `{"terms": ["KRW=X"]}` and asserts no default-bundle term leaks in.
- [x] The default bundle is exposed through a new `WatchlistImpactStatus` value `DEFAULT_BUNDLE` (distinct from `UNCONFIGURED`) so site rendering, Telegram rendering, and visual cards can show a small "기본 바스켓" badge identifying the source. The badge text is rendered behind a single `briefing/watchlist.py::DEFAULT_BUNDLE_BADGE_LABEL` chokepoint.
- [x] Telegram summary surface (notifier) honours the new status: a default-bundle-only segment receives the same single-line market snapshot it does today, with one extra `(기본 바스켓)` suffix on the ⑤ tag — never an alarm or warning.
- [x] Visual card surface (`visuals/cards.py::WatchlistRelevanceCard`) renders the bundle status row identically to the configured-watchlist row except for the same `(기본 바스켓)` badge. No layout reflow.
- [x] Per-segment resolver (`WatchlistConfig.for_segment_scope`) compatibility: when the on-disk file is empty / missing, the default bundle resolves identically across all three segments (no per-segment override). When the on-disk file has scopes, default bundle is not activated.
- [x] Logged once per pipeline run at INFO level: `watchlist config not found, using DEFAULT_CORE_ALIASES (N terms)`. Never logged at WARNING — this is a normal Day-1 path, not an error.
- [x] Full quality gate green: `ruff check` ✅, `ruff format --check` ✅, `mypy --strict src/` ✅, `pytest -q` ✅, `mkdocs build --strict` ✅.

---

## Steps

### Step 1 — Loader Default Bundle Activation

- [x] Modify `briefing/watchlist.py::load_watchlist_config` so that the existing "no path / unreadable / empty JSON" branches return `WatchlistConfig.from_default_bundle()` instead of `WatchlistConfig.empty()`.
- [x] Add `WatchlistConfig.from_default_bundle()` classmethod that constructs a config whose `terms` is the union of all `DEFAULT_CORE_ALIASES` keys, whose `weights` is empty (no preferential weighting; alphabetical sort wins on ties), and whose `scopes` is `{}` (root-only resolver).
- [x] Add `WatchlistConfig.is_default_bundle: bool` property (computed from a private `_is_default_bundle` flag set inside `from_default_bundle`) so downstream surfaces can branch.
- [x] Files affected:
  - `src/investo/briefing/watchlist.py`
- [x] Unit tests added at `tests/unit/briefing/test_watchlist_default_bundle.py`:
  - missing-path → bundle activates with N terms (N matches `len(DEFAULT_CORE_ALIASES)`).
  - empty-JSON → bundle activates.
  - unreadable-file → bundle activates and a single INFO log line is emitted.
  - on-disk-config-present → bundle does **not** activate (anti-regression: user-authored exclusion preserved).
  - on-disk-config-with-only-`KRW=X` → result has only `KRW=X` (no NVDA / BTC leakage).

### Step 2 — Status Enum Extension

- [x] Extend `WatchlistImpactStatus` enum (`briefing/watchlist.py`) with `DEFAULT_BUNDLE` distinct from `UNCONFIGURED`. Routing logic: `is_default_bundle && match_count > 0 → DEFAULT_BUNDLE`; `is_default_bundle && match_count == 0 → UNCONFIGURED` (no covered candidates so the bundle can't help).
- [x] Add `DEFAULT_BUNDLE_BADGE_LABEL = "기본 바스켓"` chokepoint in the same module so site / Telegram / card surfaces share one literal.
- [x] Files affected:
  - `src/investo/briefing/watchlist.py`
- [x] Anti-regression test in `tests/unit/briefing/test_watchlist_default_bundle.py`:
  - status routing: bundle + matches → `DEFAULT_BUNDLE`; bundle + no matches → `UNCONFIGURED`; configured + matches → `NORMAL` (unchanged); configured + no matches → `PARTIAL` (unchanged).
  - badge label literal pinned (1 test).

### Step 3 — Site Markdown Surface

- [x] Update `briefing/pipeline.py::render_watchlist_impact` (or the site-rendering helper that currently consumes `WatchlistImpactStatus`) to render the badge after the ⑤ section header text when status is `DEFAULT_BUNDLE`. Format: `### ⑤ 주요 종목 (기본 바스켓)` for the default-bundle path; configured path is unchanged.
- [x] Files affected:
  - `src/investo/briefing/pipeline.py` (header rendering)
  - possibly `src/investo/briefing/watchlist.py::render_watchlist_impact` if the rendering chokepoint already lives there
- [x] Unit tests added at `tests/unit/briefing/test_watchlist_default_bundle.py`:
  - default-bundle path renders the `(기본 바스켓)` suffix on the ⑤ header.
  - configured path renders the unchanged `### ⑤ 주요 종목` header (anti-regression).

### Step 4 — Telegram Summary Surface

- [x] Update `notifier/summary.py::build_segmented_summary` to consume the new `DEFAULT_BUNDLE` status and append `(기본 바스켓)` to the ⑤ tag in the per-segment block. The single-line market snapshot is unchanged. No new env var; no operator alert path.
- [x] Files affected:
  - `src/investo/notifier/summary.py`
- [x] Unit tests added at `tests/unit/notifier/test_summary.py`:
  - default-bundle status surfaces the `(기본 바스켓)` suffix in the rendered summary.
  - configured status does not (anti-regression).

### Step 5 — Visual Card Surface

- [x] Update `visuals/cards.py::WatchlistRelevanceCard` (or the card builder that consumes `WatchlistImpactStatus`) to read `DEFAULT_BUNDLE_BADGE_LABEL` and append it to the card title row when status is `DEFAULT_BUNDLE`. Keep dimensions and layout identical (use the existing subtitle slot — do not introduce a new row).
- [x] Files affected:
  - `src/investo/visuals/cards.py`
- [x] Unit tests added at `tests/unit/visuals/test_watchlist_card.py`:
  - default-bundle card SVG contains the `기본 바스켓` literal in the subtitle slot.
  - configured card SVG does not (anti-regression).

### Step 6 — Verification

- [x] Run targeted watchlist tests + the full quality gate.
- [x] Automated verification covers the no-config path with default-bundle matches and badge rendering across site text, Telegram summary, and visual cards.
- [x] Anti-regression verifies an on-disk config is honoured exclusively with no bundle leak.

---

## Project rule compliance

- **Anthropic SDK ban**: not applicable — no LLM call introduced.
- **Module boundary**: changes touch `briefing/`, `notifier/`, `visuals/` (already shared via the orchestrator entry point); no new cross-module import.
- **R10 (record/replay fixtures, no fabrication)**: not applicable — no new external HTTP source.
- **R13 (secret hygiene)**: not applicable — no new env var, no new secret.
- **Disclaimer enforcement**: untouched — `publisher.verify_disclaimer` remains the gate.
- **Channel separation**: untouched — public channel ⇋ operator chat distinction preserved.

---

## Quality gate

- [x] `uv run ruff check .` ✅
- [x] `uv run ruff format --check .` ✅
- [x] `uv run mypy --strict src/` ✅
- [x] `uv run pytest -q` ✅ (expect ~10-15 new tests)
- [x] `uv run mkdocs build --strict` ✅

---

## Out of scope

- **User-customizable default bundle** — the bundle is hard-coded in `DEFAULT_CORE_ALIASES`; users wanting a different default must author a `watchlist.json`. (Persona #2 secondary wish: "사용자가 자기 기본 바스켓을 환경변수로 덮어쓸 수 있어야 한다" — defer to a follow-up unit if requested; not promised here.)
- **Per-segment default bundles** — all three segments share the same bundle. Per-segment defaults are a future extension if persona #2 / persona #4 ask for them.
- **Weighting in default bundle** — bundle entries all have weight `0.0`; no preferential ordering. Persona #2 wishes for "메이저 종목이 위에 오면 좋다" are deferred to u33-style explicit weighting (already shipped for configured paths; default bundle stays uniform to avoid editorial bias).
- **Config-file scaffolding** — this unit deliberately does not write a starter `watchlist.json` to disk. Writing files outside `archive/` and `site_docs/` is a publisher concern and would conflict with the user's expectation that no config means default behaviour. Documenting "how to author your own watchlist.json" in the README is a separate ops task.

---

## Open questions

- None blocking. The default bundle already exists in code (`briefing/watchlist.py:DEFAULT_CORE_ALIASES`); this unit only changes the loader's empty-state branch and adds a status / badge surface. No external credential, no new fixture session.
