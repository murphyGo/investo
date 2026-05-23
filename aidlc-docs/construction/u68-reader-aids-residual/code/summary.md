# u68 reader-aids-residual — Code Generation Summary

**Date**: 2026-05-24
**Unit**: u68 reader-aids-residual
**Status**: Complete (3/3 steps)

## Goal

Close the single genuine residual of the 2026-05-24 reader-facing review
Gaps C/D: the glossary header callout re-announced the SAME terms
(ETF/EPS/VIX/CPI) every day as "이번 시황에서 처음 등장한 용어" because the
auditor had no cross-day memory — making the "처음 등장한" claim false on
day 2+ and defeating the once-learned reader-aid purpose. Make the callout
carryover-aware so it shows only terms genuinely new within a recent
trading-day window. No new source, schema, prompt rule, LLM call, or
library.

## Confirm-Then-Extend Audit (DoD #1 — done before any code)

| Residual candidate | Status | Code evidence | True residual? |
|---|---|---|---|
| C — watchpoint actionability | Already complete (u64) | u64 watchlist-entity-matching-and-actionability delivers the watchpoint template + actionability validator; unit-of-work.md excludes overlap | No — out of scope |
| D — glossary position (top-of-document callout) | Already complete (u40) | `render_glossary_callout` renders `> **용어 가이드**`; wired into the document header in `briefing/pipeline.py` (above 오늘의 결론) | No — fully wired |
| D — inline first-use glossing variant (optional) | Not implemented; optional | No in-body parenthetical glosser exists; only the header callout. unit-of-work.md marks this "(a) optional inline first-use glossing" | No — explicitly optional; deferred to TECH-DEBT (DEBT-070) |
| D — carryover §⑥→next-day §② resolved/unresolved echo | Already complete (u52) | `load_carryover` walks ≤3 trading days, splits resolved/unresolved; `render_carryover_block`/`inject_carryover_block` emit the §②/§③ table; prompt rules CARRY-1/CARRY-2 drive the §② citation; orchestrator wires it | No — fully implemented |
| D — glossary callout repeats the SAME terms every day | **REAL DEFECT** | `audit_glossary_compliance` built its `seen` set fresh per call, scoped to one document — no cross-day state existed anywhere | **Yes — the only genuine u68 residual** |

**Conclusion**: Gaps C/D are ~95% already delivered. u68 fixes exactly the
cross-day callout repetition and nothing else.

## Key Deliverables

- `briefing/glossary.py`:
  - `collect_recently_glossed(archive_root, segment, today, *, lookback=3)` — a pure, clock-injected helper reusing the u52 carryover archive-walk pattern. Walks the same segment's prior archives (`archive_root/segment/YYYY/MM/YYYY-MM-DD.md`), weekend-skip, bounded to ≤3 loaded trading days / ≤21 calendar days (`_MAX_CALENDAR_DAYS`). Collects a term as "already glossed" when it appeared with an immediate Korean paren gloss (`_has_immediate_korean_gloss`) OR inside a prior `> **용어 가이드**` callout line. Missing dir / `OSError` / malformed → no contribution, no raise.
  - `audit_glossary_compliance(... already_glossed: set[str] | None = None)` — extended with an optional suppression set; canonical keys in the set are dropped from the returned gaps. Default `None`/empty → byte-equal to the prior output (back-compat).
- `briefing/pipeline.py`: `_enhance_reader_experience` / `generate_briefing` take an optional `archive_root: Path | None`; computes the suppression set and feeds it to `audit_glossary_compliance` before `render_glossary_callout`. Empty gap list → existing `render_glossary_callout([]) == ""` path omits the line (no empty callout).
- `orchestrator/pipeline.py`: injects `archive_root=ARCHIVE_ROOT` via the deferred-import seam u52 uses (preserves the `monkeypatch.setattr(paths, "ARCHIVE_ROOT", tmp)` test seam).
- Tests: 25 new tests — suppression helper (gloss-in-paren detected, gloss-in-prior-callout detected, segment-scoping, weekend-skip, bounded-lookback, malformed-degrade, zero-lookback, unglossed-not-suppressed) + pipeline-level 2-day no-repeat + fresh-repo no-regression + re-publish idempotency.

## AC Traceability

| AC | Statement | Status | Evidence |
|----|-----------|--------|----------|
| AC-68.1 | A term glossed in any prior ≤N trading-day archive for the same segment is absent from today's `GlossaryGap` list | MET | `collect_recently_glossed` + `already_glossed` drop in `audit_glossary_compliance`; helper unit tests (paren-gloss + prior-callout detection) |
| AC-68.2 | Empty/default suppression set reproduces the existing output byte-for-byte | MET | `already_glossed` defaults to `None`/empty → byte-equal; back-compat test |
| AC-68.3 | On a 2nd consecutive day for the same segment, a day-1 term does not reappear in day-2's callout | MET | pipeline-level 2-day no-repeat test |
| AC-68.4 | Fresh repo (no prior archive / `archive_root=None`) renders the callout exactly as today | MET | `archive_root=None` → empty set → today-only; fresh-repo no-regression test |
| AC-68.5 | Same `(segment, date, archive)` re-publish yields a byte-equal callout (FR-006) | MET | idempotency test |

Additional cases covered: segment-scoping, weekend-skip, bounded-lookback, malformed-degrade, zero-lookback, unglossed-not-suppressed.

## Confirm-Then-Extend Audit Table (C/D already-implemented basis)

See the Confirm-Then-Extend Audit above. C (u64) and the non-defect parts
of D (u40 header callout, u52 carryover) were confirmed complete by code
inspection before any code was written; u68 extended only the cross-day
suppression seam.

## FD Divergences Ratified

- u40 had no formal `functional-design/` directory at u68 time — glossary
  logic was documented only via the u40 plan + code summary. To host this
  extension, `functional-design/business-logic-model.md` and
  `business-rules.md` were authored under
  `aidlc-docs/construction/u40-financial-acronym-glossary/` (the owning
  glossary unit). `L-glossary.1`/`R-glossary.1..3` re-state the shipped
  u40 baseline; `L-glossary.2`/`R-glossary.4` carry the u68 extension
  (`(extension 2026-05-24)`).
- Lookback counts LOADED trading days, not calendar position. On a sparse
  archive the walk can reach further back than 3 calendar days, capped by
  `_MAX_CALENDAR_DAYS=21`. This matches u52 carryover semantics and is
  documented in the helper docstring — recorded here as the one
  intentional deviation from a naive "last 3 calendar days" reading.

## TECH-DEBT Registered

- **DEBT-070** (Low) — Inline first-use glossing variant (in-body
  parenthetical auto-gloss beyond the header callout). Optional per
  unit-of-work; deferred. The header callout + cross-day suppression (u68)
  covers the reader-aid need for a 1-person tool; in-body auto-gloss risks
  distorting LLM prose and is unproven ROI.

## Verification Gate

| Gate | Result |
|------|--------|
| `ruff check` | clean |
| `ruff format --check` (changed scope) | clean |
| `mypy --strict` | clean (131 files) |
| `pytest -q` | 2443 passed (+25 new u68 tests) |
| `mkdocs build --strict` | clean |

Lead re-verification: 25 new tests pass; `glossary.py` does not import
`publisher.paths` (module boundary intact — `archive_root` injected by
orchestrator); no Anthropic SDK / paid API / new library introduced; no
secret in the archive walk or callout (R13 clean); briefing↔publisher
boundary preserved.
