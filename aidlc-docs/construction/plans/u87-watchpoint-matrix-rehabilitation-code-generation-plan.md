# Code Generation Plan: `u87 watchpoint-matrix-rehabilitation`

**Date**: 2026-05-31
**Unit**: u87 watchpoint-matrix-rehabilitation
**Stage**: Code Generation
**Status**: Backlog / Planned (ready — no blocked prerequisites)
**Source**: briefing-unit-planner review of the 2026-05-26 generated briefings (all three segments) + escalation of DEBT-074.
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u72 watchpoint-action-matrix — the owner unit. This unit refines its renderer; it does **not** replace it.
- u64 watchpoint-entity-matching-and-actionability — owns the `source + trigger + implication` structured-bullet contract and the regexes (`_WATCHPOINT_SOURCE_RE` / `_WATCHPOINT_TRIGGER_RE` / `_WATCHPOINT_IMPLICATION_RE`) reused by u72. **Not reimplemented here.**
- u56 compliance-language-and-observational-tags — the forbidden-phrase / observational boundary. Preserved unchanged.
- `briefing/trace_footer.py` — produces the `- \`input_hash\`: \`…\`` diagnostic bullet that currently leaks into §⑥ (read-only understanding; not modified).

---

## Problem Statement

In the 2026-05-26 briefings the §⑥ "오늘의 관전 포인트" matrix is **dead weight across all three segments** and additionally **leaks broken markup and a diagnostic hash** into a reader-facing table.

Concrete evidence (`archive/{domestic-equity,us-equity,crypto}/2026/05/2026-05-26.md`, §⑥):

1. **Universal `데이터부족` (D1)** — every row of every segment renders `현재 = —`, `상방/하방/신뢰도 = 데이터부족`, `섹션 내 관심 영향 = —`. The 6-row table conveys zero information.
2. **Broken markdown-link fragments + dangling particles in the 관찰 신호 column (D1b)** — e.g. us-equity rows `[AAPL](https://www.nasdaq.com/…` and `[AZO](https://www.nasdaq.com/m…` (a markdown link truncated mid-URL), and `원/달러 환율 1,499.83원이` / `기관 순매수 +8,168억원 독주 구도가` / `BTC-USD가` (a label ending on a bare Korean particle with no predicate).
3. **Diagnostic-hash leak (D1c)** — the crypto §⑥ matrix carries a row `` `input_hash`: `1ee42e89b281` `` — an internal trace-footer diagnostic bullet rendered as an observation signal.

### Root causes (verified in source)

- **D1**: `watchpoint_matrix._build_row` calls `_is_structured(bullet)`, which requires `_WATCHPOINT_SOURCE_RE` **and** `_WATCHPOINT_TRIGGER_RE` **and** `_WATCHPOINT_IMPLICATION_RE` to all match (the u64 contract). The Stage-2 §⑥ bullets the LLM currently emits are short fragments that never satisfy all three, so **every** bullet falls through to `WatchpointRow.data_limited(...)`. This is the under-population flagged by **DEBT-074**.
- **D1b**: `_short_signal` truncates at the first particle separator (`가 /이 /는 /은 /：`) within 30 chars, or else `head[:30] + "…"`. A markdown-link bullet has no separator in its first 30 chars, so it is cut mid-URL → broken `[AAPL](https://…`. A bullet beginning `원/달러 환율 1,499.83원이 …` is cut right after the particle → dangling `…원이`.
- **D1c**: `render_watchpoint_matrix` extracts bullets with `_BULLET_RE = ^\s*[-*]\s+(.+?)$` over the entire §⑥ body region. The trace-footer diagnostic lines (`- \`input_hash\`: \`…\``, `stage1_hash`, `stage2_hash`) sit inside that region at render time and are captured as "bullets", then slotted into the matrix.

---

## Goal

§⑥ either (a) presents at least one **genuinely structured** observational row, or (b) collapses to a single honest data-limited note — **never** a multi-row wall of `데이터부족`, **never** a broken markdown fragment, and **never** a diagnostic token. A reader scanning §⑥ on mobile should either learn one concrete watch condition or be told plainly that none could be structured today.

---

## Existing Coverage / Deduplication

- **u72 owns** the §⑥ matrix renderer (`publisher/watchpoint_matrix.py`) and its Stage-2 prompt rule. This unit refines that renderer + prompt; it adds **no** new module and **no** new public matrix API.
- **u64 owns** the structured-bullet contract + regexes. This unit **reuses them unchanged** (`_is_structured` stays the gate; the fix is on the *input* the LLM produces and on *non-observation* lines that should never reach the gate).
- **DEBT-074** ("clause-slotting heuristic under-population → graceful 데이터부족") is **escalated and subsumed by this unit** — u87 closes it by (i) making the Stage-2 prompt emit populatable bullets and (ii) collapsing the all-`데이터부족` state instead of rendering it. On completion, mark DEBT-074 resolved-by-u87.
- **Explicitly NOT duplicated**: u88 watchlist public-impact-line sanitization (the `[boundary-term]`/`[structured-symbol]` leak on the "내 관심 자산 영향" line is a *different* surface), u89 crypto numeric formatting, u90 meaning-line completeness, u91 observational-tag prose leakage. No new confidence enum (the closed `{높음,보통,낮음,데이터부족}` set is reused). No change to u56 compliance scanning.

---

## Scope Boundary

**In scope** (`publisher/watchpoint_matrix.py` + `briefing/prompts.py` only):
1. A §⑥ bullet **pre-filter** that drops non-observation lines (trace-footer diagnostic / backtick-key lines, bullets that are only a bare link, empty lines) before row building.
2. `_short_signal` hardening: unwrap markdown links to their link text before truncation; never emit a truncated URL; trim a trailing bare-particle so a label never ends on a dangling 조사.
3. An **all-`데이터부족` collapse**: when no usable observation row survives, render a single compact data-limited note instead of a ≥2-row table of `데이터부족`.
4. A **Stage-2 §⑥ prompt** refinement so each watchpoint bullet carries source + (상방/하방) trigger + implication in one bullet — the shape `_is_structured` already expects — so real bullets populate non-`데이터부족` rows.

**Out of scope**:
- The watchlist "내 관심 자산 영향" line match-token leak (→ u88).
- Funding-rate / numeric over-precision formatting (→ u89).
- "그래서 의미는?" meaning-line truncation (→ u90).
- `[데이터부족]`/`[상승 관찰]` bracket-tag leakage into 결론/§① prose (→ u91).
- Any new matcher, new confidence label, or change to u56 compliance scanning.
- Any reordering of the `segment_reader_format.py` pass chain (ordering is load-bearing — preserve it).

---

## Stage Decision

- **Functional Design: Skipped.** Presentation-contract refinement over the existing u72 renderer + prompt; introduces no new domain entity, no new cross-module contract, no new data model. The matrix schema and confidence enum are already fixed by u72.
- **NFR Requirements: Skipped.** No new dependency, source, secret, or runtime cost; pure `str -> str` transform + Stage-2 prompt text. Reuses NFR-004 disclaimer/compliance, R13 hygiene, and the existing static-site output contract. The diagnostic-leak fix (AC-87.1) *strengthens* R13 posture but adds no new NFR surface.
- **Source of requirements**: `docs/requirements.md` FR-002 (AI briefing), FR-004 (notification summary surface), FR-009 (reader-facing format), FR-012 (compliance language); DEBT-074; briefing-unit-planner review of 2026-05-26.

---

## Implementation Steps

### Step 1 — §⑥ bullet pre-filter (drop non-observation lines) `[ ]`
- [ ] In `publisher/watchpoint_matrix.py`, add a pure predicate `_is_observation_bullet(bullet: str) -> bool` and a `_DIAGNOSTIC_LINE_RE`. Reject a bullet when:
  - it matches a backtick-wrapped diagnostic key line — pin `_DIAGNOSTIC_LINE_RE = re.compile(r"^`?[a-z][a-z0-9_]*`?\s*[:：]")` so `` `input_hash`: … ``, `stage1_hash: …`, `stage2_hash: …`, `input_hash: …` are all dropped; (note: full-width colon `：` included);
  - after stripping markdown links and whitespace it contains **no** Hangul syllable (`re.search(r"[가-힣]", stripped)` is None) — i.e. a bare-link or pure-symbol bullet;
  - it is empty/whitespace.
- [ ] In `render_watchpoint_matrix`, apply the filter to the `_BULLET_RE`-extracted bullets **before** `build_watchpoint_rows`: `bullets = [b for b in raw_bullets if _is_observation_bullet(b)]`. Keep the existing `if not bullets and not coverage_limited: return text` early-out (now also covers "all bullets filtered out").
- [ ] Pin the exact filter behavior in a comment referencing AC-87.1.

### Step 2 — `_short_signal` markdown-safety + dangling-particle trim `[ ]`
- [ ] Add a module-level `_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:[^)]*)\)")` and unwrap links to their text **at the top of `_short_signal`**: `head = _MD_LINK_RE.sub(r"\1", head)`. This guarantees no `](http…` fragment can survive truncation (AC-87.2). (Do not reuse a `briefing/` regex — keep the publisher module boundary; a local constant is correct.)
- [ ] Add a `_TRAILING_PARTICLE_RE = re.compile(r"(?:이|가|은|는|을|를|와|과|도|의|에|로|으로)\s*…?$")` and, after the existing truncation, strip a trailing bare particle so a signal never ends on a dangling 조사 (AC-87.3). Re-append `…` only if the source was actually truncated.
- [ ] Keep the existing ≤30-char + separator behavior otherwise (do not regress the populated-row labels).

### Step 3 — all-`데이터부족` collapse `[ ]`
- [ ] Add `DATA_LIMITED_NOTE: Final[str] = "> **관전 포인트**: 구조화 가능한 관찰 신호가 부족합니다 — 본문 §②·§④ 참조"` (exact string pinned).
- [ ] In `render_watchpoint_matrix`, after building `rows`, if **every** row has `confidence == DATA_LIMITED_CONFIDENCE` (or `rows` is empty), replace the table body with `DATA_LIMITED_NOTE` (a single blockquote line) instead of `render_matrix_table(rows)`. Preserve the existing idempotency guard (a same-day re-run that already contains either the matrix header **or** `DATA_LIMITED_NOTE` returns `text` unchanged — extend the idempotency check to also detect the note).
- [ ] Keep the existing `coverage_limited` single-`데이터부족`-row path collapsing to the same note (consistency).
- [ ] Preserve the existing data-limited WARN log (`watchpoint_matrix.data_limited_rows`), and additionally emit it (count = total bullets) when the collapse fires, so operators still see under-population.

### Step 4 — Stage-2 §⑥ prompt contract so bullets populate `[ ]`
- [ ] In `briefing/prompts.py`, strengthen the §⑥ Stage-2 rule (the existing u72 observational/banned-advice block) so **each** §⑥ bullet is written as one self-contained observational sentence carrying: (a) a source/anchor reference, (b) an upside confirm condition **and** a downside confirm condition (the 상방/하방 triggers), and (c) a section-local implication — matching the `source + trigger + implication` shape `_is_structured` requires. Keep it observational only: no 매수/매도/목표가/결과예측 (u56 boundary unchanged).
- [ ] Add one or two concrete in-prompt examples of a populatable bullet vs a rejected fragment so the model emits the structured shape. Keep the prompt compact (this is the single highest-leverage fix for D1).

### Step 5 — Tests + docs + gate `[ ]`
- [ ] Extend `tests/unit/publisher/test_watchpoint_matrix.py` (create if the file is named differently — confirm with `rg -l watchpoint tests/unit/publisher`) with fixtures built from the real 2026-05-26 defect shapes:
  - a §⑥ body containing a `- \`input_hash\`: \`1ee42e89b281\`` line → no row's signal contains `input_hash` or a backtick (AC-87.1);
  - a markdown-link bullet `- [AAPL](https://www.nasdaq.com/articles/...) 신고점 …` → signal is `AAPL …`-style text, never contains `](http` (AC-87.2);
  - a `- 원/달러 환율 1,499.83원이 …` bullet → signal does not end on `원이`/a bare particle (AC-87.3);
  - all bullets unstructured → output contains `DATA_LIMITED_NOTE` and **no** matrix header (AC-87.4);
  - one fully-structured source+trigger+implication bullet → a populated row with `현재` set, at least one of 상방/하방 non-`데이터부족`, and confidence ∈ {높음,보통,낮음} (AC-87.5);
  - idempotency: re-running over output containing `DATA_LIMITED_NOTE` returns it unchanged; disclaimer/byte-preservation outside §⑥ (AC-87.7).
- [ ] Add a `tests/unit/briefing/test_prompts.py` assertion that the §⑥ Stage-2 rule text mentions the source+trigger+implication contract and bans advice wording.
- [ ] Run `rg` to confirm no production code outside `publisher/watchpoint_matrix.py` + `briefing/prompts.py` changed.
- [ ] On completion, mark **DEBT-074 resolved-by-u87** in `docs/TECH-DEBT.md` and decrement its priority count.

---

## Acceptance Criteria

- **AC-87.1** A §⑥ body containing a trace-footer `- \`input_hash\`: \`…\`` line (or `stage1_hash`/`stage2_hash`) produces **no** matrix row whose signal contains `input_hash` or a backtick — the diagnostic line is filtered before row building.
- **AC-87.2** A §⑥ bullet that is or contains a markdown link never yields a cell containing `](http` or an unbalanced `[`/`(`; the link **text** is used as the signal.
- **AC-87.3** A signal label never ends on a bare Korean particle from the pinned trim set (e.g. never `…원이`, `…구도가`, `BTC-USD가`).
- **AC-87.4** When no observation bullet is structured/usable, §⑥ renders the single pinned `DATA_LIMITED_NOTE` blockquote and **no** matrix header — never a ≥2-row table of all `데이터부족`.
- **AC-87.5** A fully-structured source+trigger+implication bullet produces a populated row: `현재` non-dash, at least one of 상방/하방 trigger non-`데이터부족`, confidence ∈ {높음,보통,낮음}. (Proves the matrix can populate, closing DEBT-074.)
- **AC-87.6** No buy/sell/target-price wording is introduced; the existing u56 / u72 watchpoint compliance tests stay green unchanged.
- **AC-87.7** The transform stays idempotent (same-day re-run is a no-op for both the matrix-header and the `DATA_LIMITED_NOTE` states) and byte-preserves every section outside §⑥ plus the disclaimer footer.

---

## Tests / Validation

- **Unit**: `tests/unit/publisher/test_watchpoint_matrix.py` (the seven fixtures above), `tests/unit/briefing/test_prompts.py` (§⑥ rule text).
- **Fixtures**: inline string fixtures derived from the 2026-05-26 defect shapes — no new recorded API fixture needed (pure `str -> str`).
- **Local gate**:
  ```bash
  ruff check src/investo/publisher/watchpoint_matrix.py src/investo/briefing/prompts.py tests/unit/publisher/test_watchpoint_matrix.py tests/unit/briefing/test_prompts.py
  ruff format --check <same paths>
  mypy --strict src/investo/publisher/watchpoint_matrix.py src/investo/briefing/prompts.py
  python -m pytest tests/unit/publisher/ tests/unit/briefing/ -q
  python -m pytest -q     # full suite, report passed count
  mkdocs build --strict
  ```

---

## Non-Goals

- Watchlist "내 관심 자산 영향" line sanitization (u88).
- Crypto funding-rate / numeric over-precision formatting (u89).
- "그래서 의미는?" meaning-line completeness (u90).
- `[데이터부족]`/`[상승 관찰]` bracket-tag prose leakage (u91).
- New matcher, new confidence enum, or any change to u56 compliance scanning.
- Reordering the `segment_reader_format.py` reader-format pass chain.
