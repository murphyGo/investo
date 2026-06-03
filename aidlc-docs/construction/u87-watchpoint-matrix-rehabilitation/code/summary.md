# u87 Watchpoint-Matrix Rehabilitation — Code Generation Summary

**Date**: 2026-05-31
**Unit**: u87 watchpoint-matrix-rehabilitation
**Status**: Complete (5/5 steps; AC-87.1..87.7 all pinned)

## Goal

§⑥ "오늘의 관전 포인트" either presents at least one genuinely structured
observational row or collapses to a single honest data-limited note — never a
multi-row wall of `데이터부족`, never a broken markdown fragment, and never a
diagnostic token. Motivated by the 2026-05-26 briefings, where §⑥ rendered as
dead weight across all three segments (universal `데이터부족`) and additionally
leaked broken markdown-link fragments, dangling Korean particles, and a
trace-footer `input_hash` diagnostic into a reader-facing table. Escalates and
subsumes DEBT-074.

## Delivered slices

### Step 1 — §⑥ bullet pre-filter (`publisher/watchpoint_matrix.py`)

- Added pure predicate `_is_observation_bullet(bullet) -> bool` + module-level
  `_DIAGNOSTIC_LINE_RE`. A bullet is rejected when it is a backtick-wrapped
  lowercase diagnostic key line (`input_hash` / `stage1_hash` / `stage2_hash`,
  full-width colon variant included), or — after markdown-link stripping — it
  carries no Hangul syllable (a bare-link / pure-symbol bullet), or it is
  empty/whitespace.
- `render_watchpoint_matrix` applies the filter to the `_BULLET_RE`-extracted
  bullets **before** `build_watchpoint_rows`. The existing
  `if not bullets and not coverage_limited: return text` early-out now also
  covers "all bullets filtered out".

### Step 2 — `_short_signal` markdown-safety + dangling-particle trim

- `_MD_LINK_RE` (local publisher constant — no `briefing/` import) unwraps
  `[text](url)` to its link text at the top of `_short_signal`, so no
  `](http…` fragment can survive truncation (AC-87.2). The same unwrap is also
  applied at `_escape_cell`, the single choke point every cell value passes
  through, so the `현재`/trigger/implication cells are URL-fragment-free too —
  AC-87.2 reads "never yields a cell containing `](http`", not only the signal.
- `_TRAILING_PARTICLE_RE` trims a trailing bare Korean 조사 via the new
  `_trim_trailing_particle(label, *, truncated)` helper; the `…` ellipsis is
  re-appended only when the source was actually truncated (AC-87.3). The
  existing ≤30-char + separator behavior is otherwise preserved.

### Step 3 — all-`데이터부족` collapse

- Added `DATA_LIMITED_NOTE: Final[str]` (exact pinned string, see below).
- After building `rows`, when every row is `데이터부족` (or `rows` is empty),
  the §⑥ body is replaced with the single `DATA_LIMITED_NOTE` blockquote
  instead of a ≥2-row table (AC-87.4). The pre-existing `coverage_limited`
  single-`데이터부족`-row path collapses to the same note (consistency).
- Idempotency guard extended: a same-day re-run that already contains the
  matrix header **or** `DATA_LIMITED_NOTE` returns `text` unchanged (AC-87.7).
- The data-limited WARN log (`watchpoint_matrix.data_limited_rows`) is
  preserved and additionally fires (count = total bullets) when the collapse
  triggers, so operators still see under-population.

### Step 4 — Stage-2 §⑥ prompt contract (`briefing/prompts.py`)

- Strengthened the existing u72 §⑥ matrix rule so each bullet is a single
  self-contained observational sentence carrying (a) a source/anchor, (b) an
  upside confirm condition **and** a downside confirm condition (상방/하방
  triggers in one bullet), and (c) a section-local implication — the exact
  `source + trigger + implication` shape `_is_structured` requires. Added one
  populatable example and two rejected-fragment examples (a bare verb-only
  bullet and a markdown-link fragment) plus an explicit ban on emitting
  `input_hash`/`stage1_hash` diagnostic tokens as bullets. Observational-only;
  no 매수/매도/목표가/결과예측 (u56 boundary unchanged).

### Step 5 — Tests + docs + gate

- `tests/unit/publisher/test_watchpoint_matrix.py`: +7 AC-87 defect-shape
  fixtures derived from the real 2026-05-26 shapes.
- `tests/unit/briefing/test_prompts.py`: +1 §⑥ rule assertion
  (`source + trigger`, populatable example, advice ban, diagnostic-token ban).
- DEBT-074 moved to Resolved Items (resolved-by-u87); Low count 33 → 32.

## Pinned strings / regexes

- `DATA_LIMITED_NOTE = "> **관전 포인트**: 구조화 가능한 관찰 신호가 부족합니다 — 본문 §②·§④ 참조"`
- `_DIAGNOSTIC_LINE_RE` pattern: `^` then an optional backtick, a lowercase key (`[a-z][a-z0-9_]*`), an optional backtick, optional whitespace, then a colon (`[:：]`, full-width variant included).
- `_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:[^)]*)\)")`
- `_TRAILING_PARTICLE_RE = re.compile(r"(?:이|가|은|는|을|를|와|과|도|의|에|로|으로)\s*…?$")`

## AC coverage

| AC | Test |
|----|------|
| AC-87.1 | `test_diagnostic_hash_line_is_filtered_before_rows_ac87_1` |
| AC-87.2 | `test_markdown_link_bullet_never_yields_url_fragment_ac87_2` |
| AC-87.3 | `test_signal_never_ends_on_bare_particle_ac87_3` |
| AC-87.4 | `test_all_unstructured_collapses_to_single_note_ac87_4` |
| AC-87.5 | `test_structured_bullet_produces_populated_row_ac87_5` |
| AC-87.6 | `test_existing_watchpoint_tests_compliance_unchanged_ac87_6` + full publisher suite |
| AC-87.7 | `test_data_limited_note_render_is_idempotent_ac87_7`, `test_render_byte_preserves_outside_section_six_ac87_7` |

## Quality gate (changed scope)

| Gate | Result |
|------|--------|
| `ruff check` (changed files) | All checks passed |
| `ruff format --check` (changed files) | 4 files already formatted |
| `mypy --strict` (changed source) | no issues in 2 source files |
| `pytest tests/unit/publisher/ tests/unit/briefing/` | **1270 passed** |
| `pytest` (full suite) | **2868 passed** |
| `mkdocs build --strict` | exit 0 (no tracked source files modified) |

`ruff format --check .` was run changed-scope only; the worktree has known
out-of-scope unformatted/untracked files. `mkdocs build` wrote only into the
gitignored `site/` dir — no tracked source file (incl. the pre-existing
out-of-scope `site_docs/watchlist/daily.md`) was modified.

## Hard-rule compliance

- Reuses u64 `_is_structured` + the three `_WATCHPOINT_*_RE` regexes UNCHANGED;
  no new matcher, no new confidence enum (closed `{높음,보통,낮음,데이터부족}`).
- No change to u56 compliance scanning; no reorder of the
  `segment_reader_format.py` reader-format pass chain.
- Module boundary preserved: `watchpoint_matrix.py` imports stdlib +
  `reader_format` regexes only; `_MD_LINK_RE`/`_TRAILING_PARTICLE_RE` are local
  publisher constants (no `briefing/` import).
- Transform stays a pure `str -> str`, idempotent for both the matrix-header
  and the `DATA_LIMITED_NOTE` states; byte-preserves everything outside §⑥ +
  the disclaimer footer.
- No Anthropic SDK; LLM only via Claude Code CLI subprocess (unchanged).
- R13: WARN extras carry only `segment` / `count`; no secret-shaped values.

## TECH-DEBT candidates

- **Cell-text richness on mixed tables**: when a §⑥ has a mix of structured and
  unstructured bullets, the unstructured ones still render as `데이터부족` rows
  inside a populated table (the collapse only fires when *all* rows are
  data-limited). The original DEBT-074 typed-evidence enrichment (plumb u55
  `CoreFact` / u52 `BriefingCarryover` / u64 `WatchlistImpact` directly into
  the row builder) remains a valid future upside to reduce those mixed-table
  `데이터부족` cells, but is no longer required to close the reader-facing
  defect. Not filed as a new DEBT item (low value; residual of resolved
  DEBT-074).

## Intentionally out of scope (per plan Non-Goals)

- Watchlist "내 관심 자산 영향" line match-token sanitization (u88).
- Crypto funding-rate / numeric over-precision formatting (u89).
- "그래서 의미는?" meaning-line completeness (u90).
- `[데이터부족]`/`[상승 관찰]` bracket-tag prose leakage (u91).
- Any new matcher, new confidence label, or change to u56 compliance scanning.
- Reordering the `segment_reader_format.py` reader-format pass chain.
