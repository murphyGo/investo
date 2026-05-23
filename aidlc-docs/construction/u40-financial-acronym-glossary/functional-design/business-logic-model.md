# Business-Logic Model — `u40 financial-acronym-glossary`

**Date**: 2026-05-09 (baseline) / 2026-05-24 (cross-day suppression extension)
**Source**: u40-financial-acronym-glossary-code-generation-plan.md (baseline) + u68-reader-aids-residual-code-generation-plan.md (extension)

This document is the technology-neutral description of how the glossary
reader-aid behaves. Concrete library calls (`re`, `pathlib`) are inputs;
the algorithms below are what code generation implements.

This FD is authored retroactively at u68 close to host the cross-day
suppression extension (`L-glossary.2`). The baseline (`L-glossary.1`)
re-states the algorithm already shipped by u40.

---

## L-glossary.1 — First-appearance compliance audit + header callout (u40 baseline)

```
rendered Stage 2 markdown (per segment)
    │
    ▼
audit_glossary_compliance(markdown, *, segment)
    │  scan body linearly, per segment scope
    │  track terms already seen in THIS document
    │  on a term's first appearance:
    │     if term ∈ BASELINE_GLOSSARY and no immediate Korean paren gloss
    │     → emit GlossaryGap(term, gloss)
    ▼
list[GlossaryGap]   (capped at 5 for render; "외 N건" suffix beyond)
    │
    ▼
render_glossary_callout(gaps)
    │  non-empty → "> **용어 가이드**: 이번 시황에서 처음 등장한 용어 — EIA(에너지정보청), ..."
    │  empty     → "" (no callout line emitted)
    ▼
prepended to the document header (above 오늘의 결론)
```

- Per-segment gloss scope: a gloss in one segment never satisfies another
  segment's first-appearance requirement.
- Informational, non-blocking: a gap never blocks publication; the LLM
  gets the rule again on the next run.

---

## L-glossary.2 — Cross-day glossed-term suppression (extension 2026-05-24, u68)

The u40 callout claims "이번 시황에서 **처음 등장한** 용어." With no memory
beyond the single document it audits, every baseline term that appears
today is reported as first-appearance — so high-frequency terms
(ETF/EPS/VIX/CPI) re-fire an identical callout every day, making the
"처음 등장한" claim false on day 2+. `L-glossary.2` scopes that claim to a
recent trading-day window.

```
archive_root (injected by orchestrator), segment, today
    │
    ▼
collect_recently_glossed(archive_root, segment, today, *, lookback=3)
    │  reuse u52 archive-walk shape (carryover_parser pattern):
    │    - step back one calendar day at a time from `today`
    │    - skip weekends (_is_weekday)
    │    - read archive_root/segment/YYYY/MM/YYYY-MM-DD.md when present
    │    - stop after `lookback` LOADED trading days
    │      OR after _MAX_CALENDAR_DAYS (21) calendar days, whichever first
    │  per loaded prior briefing, collect a term as "already glossed" if:
    │    (a) it appeared with an immediate Korean paren gloss
    │        (reuse _has_immediate_korean_gloss), OR
    │    (b) it appeared inside that day's `> **용어 가이드**` callout line
    │  missing dir / OSError / malformed file → contributes nothing, no raise
    │  archive_root is None (fresh repo / data-limited) → return empty set
    ▼
already_glossed: set[str]   (canonical BASELINE_GLOSSARY keys)
    │
    ▼
audit_glossary_compliance(markdown, *, segment, already_glossed=already_glossed)
    │  same as L-glossary.1, but drop any gap whose canonical key
    │  ∈ already_glossed before returning
    ▼
list[GlossaryGap]  (recent-window-new terms only)
    │
    ▼  render_glossary_callout(...)  (unchanged; empty → no line)
```

- **Back-compat seam**: `already_glossed` defaults to `None`/empty →
  `audit_glossary_compliance` reproduces the L-glossary.1 output
  byte-for-byte (no regression for existing callers/tests).
- **Wiring**: `briefing/pipeline.py` (`_enhance_reader_experience` /
  `generate_briefing`) takes an optional `archive_root: Path | None`;
  `orchestrator/pipeline.py` injects `archive_root=ARCHIVE_ROOT` via the
  same deferred-import seam u52 uses (preserves the
  `monkeypatch.setattr(paths, "ARCHIVE_ROOT", tmp)` test seam).
- **Module boundary**: `glossary.py` does NOT import `publisher.paths`;
  `archive_root` is injected by the orchestrator. The briefing↔publisher
  boundary is preserved.
- **Lookback semantics note**: `lookback` counts LOADED trading days, not
  calendar position. On a sparse archive the walk can reach further back
  than 3 calendar days, capped by `_MAX_CALENDAR_DAYS=21`. This matches
  u52 carryover semantics and is documented in the helper docstring.
