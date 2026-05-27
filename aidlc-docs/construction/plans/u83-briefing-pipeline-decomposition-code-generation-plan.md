# Code Generation Plan: `u83 briefing-pipeline-decomposition`

**Date**: 2026-05-28
**Unit**: u83 briefing-pipeline-decomposition
**Stage**: Code Generation (refactor)
**Status**: Complete — 7/7 steps (Step 4b SLAP re-leveling done)
**Source**: 2026-05-28 abstraction review — `briefing/pipeline.py` (god-module)
**Estimated Effort**: ~6-8 h (largest briefing change in the wave)
**Dependencies**: **u79** (briefing regex patterns centralized — soft but recommended)
**Wave**: 14 — read `wave-14-abstraction-refactor-overview.md` first; its Refactor Contract governs this unit. **Behavior-preserving is mandatory: generated briefing markdown must be byte-identical.**

---

## Problem Statement

`briefing/pipeline.py` is 1918 lines / 88 functions and tangles ~11 distinct responsibilities behind one entry point (`generate_briefing`, ~L1709-1907, itself a 200-line state machine):

1. LLM subprocess orchestration — `_classify` / `_synthesize` retry loops (~L1527-1701)
2. Classification JSON parsing + recovery — `_load_classification_payload`, `_maybe_flip_inverted_assignments` (~L415-502)
3. Text normalization — `parse_six_sections` (~L605-656), `_clean_summary_line`, `_split_into_sentences` (~L1133-1189)
4. Prompt field truncation / URL rendering (~L880-891)
5. Markdown rendering — `_render_grouped_sections`, `_render_unassigned` (~L659-748)
6. Section planning — `build_section_plan` (~L565-594)
7. Reader-experience enhancement — `_enhance_reader_experience` (~L1457-1519)
8. Summary extraction — `_summary_sentence`, `_build_summary_header` (~L1222-1286)
9. Lineage tracing — `_macro_lineage_*` (~L772-858)
10. Coverage badging — `_render_coverage_badge`, `_classify_failure_reason` (~L1289-1418)
11. Context-block rendering — recent / carryover / bundle / lookahead (~L904-1064)

The file imports from a dozen sibling modules; locating any one responsibility means scanning the whole file.

---

## Goal

Decompose `pipeline.py` into a small set of cohesive sub-packages, leaving `generate_briefing` as a thin orchestrator that wires the stages. Public symbols (`Briefing`, `ClassificationResult`, `SectionPlan`, `generate_briefing`, and anything imported elsewhere) keep their import path via re-export from `briefing/pipeline.py` (or a package `__init__.py`). **Generated markdown is byte-identical for every fixture.**

Proposed target layout (the implementer may adjust module names but must keep the responsibility grouping):

```
briefing/
  _core/
    orchestration.py     # _classify, _synthesize, retry/budget loops
    classification.py    # ClassificationResult, JSON load + recovery, inversion flip
    section_planning.py  # SectionPlan, build_section_plan
  _assembly/
    text_normalize.py    # parse_six_sections, _clean_summary_line, _split_into_sentences
    summary_extraction.py# _summary_sentence, _build_summary_header
    markdown_render.py    # _render_grouped_sections, _render_unassigned  (output markdown rendering ONLY)
    prompt_fields.py     # _truncate_prompt_field, _render_prompt_url  (LLM-INPUT shaping — NOT output rendering)
  _reader_enhance/
    coverage_badge.py    # _render_coverage_badge, _classify_failure_reason
    enhancement.py       # _enhance_reader_experience
    context_render.py    # recent / carryover / bundle / lookahead context blocks  (SINGLE home for context-block rendering)
    lineage.py           # _macro_lineage_* (or reuse existing briefing/lineage.py)
  pipeline.py            # generate_briefing orchestrator + public re-exports
```

> **Corrected after review (2026-05-28):** (1) context-block rendering lives ONLY in `_reader_enhance/context_render.py` — an earlier draft double-listed it under `markdown_render.py` too (an internal contradiction / Shotgun-Surgery risk). A presentation change to a rendered block must touch one module. (2) Prompt-field truncation is an **LLM-input-shaping** concern (changes for a prompt reason), not output rendering — it gets its own `prompt_fields.py`, not folded into `markdown_render.py`.

---

## Existing Coverage / Deduplication

- Some responsibilities already have sibling modules (`briefing/lineage.py`, `briefing/extract.py`, `briefing/context.py`, `briefing/segments.py`, `briefing/prompts.py`). **Move into the existing module when one already owns the concern** rather than creating a parallel one — e.g. lineage helpers should consolidate with `briefing/lineage.py` if that is their natural home.
- Regex/markers used by the moved code come from u79's `briefing/_text/patterns.py`.
- The data-limited shortcut path (`_build_data_limited_body`) and the dual disclaimer/leak-guard calls in `generate_briefing` are behavior-load-bearing — preserve their exact sequencing when extracting.

---

## Scope Boundary

In scope:
- Splitting `pipeline.py` into the sub-packages above; `generate_briefing` becomes a thin wire-up; full re-export of public names.

Out of scope:
- Any change to prompts, LLM invocation behavior, classification logic, or rendered markdown.
- Introducing the validator/gate protocol (that is **u85**; the checks called from the pipeline are wrapped there, not here).
- Changing the `Briefing` model.

---

## Stage Decision

- **Functional Design — SKIP.** Structural decomposition over existing briefing logic; no new domain entity (the existing entities are unchanged).
- **NFR Requirements — SKIP.** No new dependency/service/secret/cost. The Claude-Code-CLI-only rule and timeout budget are preserved exactly.

---

## Implementation Steps

> **Discipline:** extract one sub-package per step and run the full briefing + integration test set after each. Do not proceed to the next step on a red gate. Each step's diff should be move-only (relocate + adjust imports), never a logic edit.

### Step 1 — extract `_core/` (orchestration, classification, section planning) `[x]`
- [x] Move `_classify` / `_synthesize` / retry loops → `_core/orchestration.py`; classification parse/recovery/inversion → `_core/classification.py`; `build_section_plan` + `SectionPlan` → `_core/section_planning.py`.
- [x] Re-export `ClassificationResult` / `SectionPlan` from `pipeline.py`.
- **Acceptance**: briefing pipeline tests green unchanged after this step alone.

### Step 2 — extract `_assembly/` (text normalize, summary extraction, markdown render) `[x]`
- [x] Move `parse_six_sections`, `_clean_summary_line`, `_split_into_sentences` → `text_normalize.py`; `_summary_sentence`, `_build_summary_header` → `summary_extraction.py`; grouped/unassigned renderers + field truncation + context blocks → `markdown_render.py`.
- **Acceptance**: tests green unchanged.

### Step 3 — extract `_reader_enhance/` (coverage badge, enhancement, context render, lineage) `[x]`
- [x] Move `_render_coverage_badge`, `_classify_failure_reason`, `_enhance_reader_experience`, context-block renderers; consolidate `_macro_lineage_*` with `briefing/lineage.py` (or `_reader_enhance/lineage.py`).
- **Acceptance**: tests green unchanged.

### Step 4 — slim `generate_briefing` (structural) `[x]`
- [x] Reduce `generate_briefing` to call the extracted stages in the existing order, including the data-limited shortcut and the disclaimer/leak-guard/footer sequence verbatim.
- [x] Confirm `pipeline.py` re-exports all previously importable public names.
- **Acceptance**: `grep -rn "from investo.briefing.pipeline import" src tests` — no caller needs an edit beyond what re-export covers.

### Step 4b — level the orchestrator body (SLAP; logic-edit explicitly permitted) `[x]`
> **Added after review (2026-05-28, guide §9.3 SLAP / §2 clean functions).** Steps 1–4 are move-only and would leave `generate_briefing` (today briefing/pipeline.py:1709-1907) at mixed abstraction levels: inline prompt-context string concatenation, the footer `enhanced_markdown += …` munging, the macro-lineage `.extend(...)` mutation, and a `Briefing(...)` constructor duplicated verbatim across the data-limited path and the main path. The "move-only diff" rule cannot fix this; this step is a **carved-out exception to Refactor-Contract item #3** — a behavior-preserving *logic edit*, proven by the u65 replay harness (byte-identical output).
- [x] Extract `_assemble_prompt_context(...)`, `_append_traceability_footer(...)`, and a single `_finalize_briefing(sections, full_markdown, segment, target_date)` that collapses the two duplicated `Briefing(...)` constructions (also a DRY fix, guide §1).
- [x] After this, `generate_briefing` should read like a paragraph of intent (one altitude); descend into a sub-function only to see a detail.
- **Acceptance**: u65 replay harness byte-identical; `generate_briefing` body contains no raw string concatenation / no duplicated `Briefing(...)`; AC-83.1 ("thin orchestrator") is met at the function level, not just the file level.

### Step 5 — behavior-preservation verification `[x]`
- [x] **Pre-flight test-brittleness audit (do FIRST, review 2026-05-28, guide §8 test-behavior-not-implementation):** classify the high-stakes briefing tests (`test_pipeline_unit.py`, `test_fake_claude_runner.py`) as behavioral vs implementation-coupled. If any assert on internal call sequences / private function names, rewrite them to assert outcomes in a SEPARATE committed step *before* extracting — otherwise contract clause "changed assertion = behavior change" misfires (false-block) or a behavior shift slips through (false-pass).
- [x] **Confirm replay-corpus failure-path coverage:** byte-identical output only proves preservation for *recorded* inputs. Verify the u65 replay corpus includes leak-guard-triggering, disclaimer-edge, and data-limited-shortcut fixtures — not only clean happy-path briefings — so the safety gates are actually exercised (guide §8 failure paths).
- [x] Run `tests/unit/briefing/*` + `tests/integration/test_pipeline.py` + the u65 replay harness; confirm generated markdown is byte-identical against recorded fixtures.
- **Acceptance**: brittleness audit done (implementation-coupled assertions rewritten in a prior commit); failure-path fixtures present; all green unchanged; replay harness reports no diff.

### Step 6 — full gate `[x]`
- [x] ruff / ruff-format / mypy --strict / pytest / mkdocs build --strict.
- **Acceptance**: full gate green.

---

## Acceptance Criteria

- **AC-83.1** — `pipeline.py` is decomposed into cohesive sub-packages; `generate_briefing` is a thin orchestrator.
- **AC-83.2** — Generated briefing markdown is byte-identical to pre-refactor for every fixture (u65 replay harness clean).
- **AC-83.3** — All public symbols keep their import path via re-export; no caller import edits beyond mechanical.
- **AC-83.4** — Every pre-existing briefing + integration test passes unchanged; Claude-CLI-only + timeout budget preserved; mypy --strict clean.

---

## Tests / Validation

- `tests/unit/briefing/test_pipeline_unit.py`, `test_fake_claude_runner.py`, `test_segments_exclusivity.py`, `test_market_anchor.py`, `test_prompts.py`, `test_watchlist.py`; `tests/integration/test_pipeline.py`; u65 replay harness — all stay green unchanged.
- Gate: full `pytest` is required (not just targeted) given the blast radius; mkdocs build --strict.

---

## Non-Goals

- Any prompt / LLM / classification / markdown behavior change.
- The validator/gate protocol (u85).
- `Briefing` model changes.
