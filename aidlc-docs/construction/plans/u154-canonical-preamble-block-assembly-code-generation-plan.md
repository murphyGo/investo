# Code Generation Plan: `u154 canonical-preamble-block-assembly`

**Date**: 2026-09-06
**Unit**: u154 canonical-preamble-block-assembly
**Stage**: Code Generation
**Status**: Backlog / partial-scope-ready — Functional Design ready; code integration blocked
**Source**: `briefing-review-20260906.md`; ten published September 1–4 segment documents
**Estimated Effort**: ~6–9 h
**Dependencies**:
- u51/u61/u71 TL;DR/summary/reflow — complete.
- u141 supplements and u144 region lifecycle — complete.
- u150 terminal Markdown link containment — ongoing in another local worktree;
  integrate its completed finalizer contract before code integration here.
- u153 summary sentence boundary — required for this unit's final-summary gate.

## Problem Statement

All ten September 1–4 documents contain two H1 titles. September 4 headers put
the hero before `한눈에 보기`, whose three lines are not rendered as a list.
`ensure_tldr_block` returns unchanged on an existing H2 without validating its
contents. `_assemble_phase_one_presentation_briefing` handles only the first
line; `PublicDocumentLayout` validates that line, allowing a duplicate H1
elsewhere in the preamble. Independent producers never establish one final
known-block order before publication.

## Goal

Final documents have one canonical title, exactly three TL;DR items and a
stable preamble where the hero follows the useful summary. Preserve the
existing table, watchlist, supplement, diagnostics and sealing contracts.

## Existing Coverage / Deduplication

- This is an integration extension to u51/u61/u71, not a generic new
  first-viewport formatting system. Existing text producers remain owners.
- u144 remains the only finalizer; extend its assembly and structural
  validation, without introducing a post-seal rewrite.
- u141 owns hero selection, insertion metadata, caption and staged files;
  move whole owned blocks, never select another asset or parse URLs for files.
- u153 owns snippet content/budget; this unit consumes that result.
- u150 owns invalid links and region dispositions; do not overwrite its
  active work or add alternative repair policy.

## Scope Boundary

In scope: canonical title deduplication, existing TL;DR shape, known preamble
block ordering, final structure and staged-artifact invariants.
Out of scope: new CSS, viewport pixel guarantees, chart/table redesign,
status/KPI wording, diagnostics relocation, source display labels, rewriting
body sections or archived documents.

## Stage Decision

Functional Design: REQUIRED — amend u144 preamble structure expectations and
freeze title-conflict and TL;DR fallback behavior. The proposed layout below
reconciles current FR-009 anchor-before-TL;DR with u71 summary-before-visuals.

NFR Requirements: SKIP — existing NFR-003/004/005/006 and R13 suffice; no new
I/O, dependency, source, secret, LLM call, runtime retry or cost.

## Fixed Contracts

1. Assemble these known blocks in order, with one blank line between Markdown
   block boundaries:
   canonical H1; segment short disclaimer; watermark; active-segment navigation;
   existing anchor table when present; `## 한눈에 보기` with exactly three
   `- ` items; conclusion/driver/caution callouts; watchlist impact line when
   present; owned hero supplement when present; existing shared macro, crypto
   indicator, channel baseline, cause-map and daily-thesis blocks in their
   current relative order; `## ①` and subsequent body.
   The anchor table stays before TL;DR per FR-009. Full diagnostics and the
   current status chip stay at their current footer location.
2. H1 identity is `# {target_date} {SEGMENT_LABELS[segment]} 시황`.
   Normalize the first generated title as today. Remove only duplicate exact
   canonical titles in the preamble outside fences/owned supplements.
   A different extra H1, or an extra H1 inside required body content, is an
   unresolved structure defect; never silently discard it as duplicate.
3. Resolve `한눈에 보기` by exact H2 and the next H2 boundary. Exclude known
   separately owned callouts/supplements before counting its content. Accept
   exactly three nonempty plain lines, or exactly three existing bullet items;
   normalize plain lines to `- ` bullets and preserve existing safe values.
   Any other shape rebuilds the three items from the canonical repaired
   conclusion/driver/caution callouts using u51's existing fallback strings.
   No fourth item, nested list, table or freeform content is silently dropped:
   move such original unsupported content into neither body nor diagnostics;
   use the whole owned TL;DR replacement, with an explicit region outcome.
4. A missing TL;DR uses the same existing callout fallback. Reuse u61's
   canonical summary validation and u153 bounding. Do not summarize the
   article again or invoke an LLM.
5. Preserve exact bytes inside visual/chart markers, URLs, captions,
   supplementary asset IDs, body sections, source diagnostics and disclaimer.
   Only block separators and the owned title/TL;DR surface may change.
   Unknown preamble regions remain in their original relative order after the
   known summary/hero cluster and before `## ①`; they are not deleted.
6. Perform normalization during phase-one assembly, after producers and
   supplements are available and before projection/repair/terminal validation.
   Reindex with the existing `PublicRegionExpectation`; no new parser
   framework or replacement lifecycle.
7. Extend terminal structure checks to enforce exactly one unfenced public
   H1, one TL;DR H2, three items, summary-before-hero and required known-block
   order. Residual violations use `structure.header_title` for H1 and new
   bounded structural codes `structure.tldr_shape` /
   `structure.preamble_order` for the others. They stay fail-closed;
   u150 link containment cannot convert structural failures to success.
8. Preserve active-survivor navigation and staged asset membership. The same
   draft/context finalized twice produces the same bytes and ordered asset
   identifiers. One or two missing segments never produce dead links.

## Implementation Steps

- [ ] Step 1 — Capture minimal synthetic preambles reproducing duplicate H1,
  unbulleted TL;DR, hero-before-summary, missing TL;DR and extra-H1 conflict.
  Use the u144 incident fixture structure and dummy staged supplement assets.
- [ ] Step 2 — Extend `publisher/reader_format/tldr.py::ensure_tldr_block`
  to normalize existing content and rebuild invalid shapes under contract 3.
  Keep content bounding in u153's helper.
- [ ] Step 3 — Add the bounded pure preamble composer in
  `publisher/reader_format/preamble.py` and invoke it from
  `public_document.py::_assemble_phase_one_presentation_briefing` with
  existing structured context/owned supplement fragments. Keep semantic
  knowledge out of the orchestrator.
- [ ] Step 4 — Add final preamble assertions to u144 layout/terminal structure
  validation. Use existing ownership for TL;DR replacement outcomes; update
  Functional Design RegionSpec documentation in the same implementation.
- [ ] Step 5 — Cover active-survivor reassembly, preserved image/chart markers,
  staged artifact IDs, body-used accounting and exact disclaimer. Regress
  u150 link transformations on the final order once its code is integrated.
- [ ] Step 6 — Run finalizer-backed and offline HTML rendering tests; record
  structural results and all prerequisite SHAs. Do not claim mobile visual
  QA unless an actual viewport was inspected.

## Acceptance Criteria

1. AC-154.1: Ten incident-shaped fixtures produce one canonical H1, one
   `한눈에 보기` H2 and exactly three unordered-list items.
2. AC-154.2: Known blocks have the pinned order; hero appears after all summary
   items/callouts and never splits a list or table.
3. AC-154.3: Extra noncanonical H1, unresolved malformed TL;DR or order defects
   fail structural validation; no evidence is silently thrown away outside
   the explicitly owned TL;DR replacement.
4. AC-154.4: Asset marker bodies, URLs, captions, staged IDs, body evidence,
   diagnostics/footer and disclaimer are byte-identical.
5. AC-154.5: Partial bundles have correct active links, summary extraction
   agrees with final text, and u150 hard-gate behavior remains intact.
6. AC-154.6: Repeated assembly/finalization is byte-stable; offline HTML parsing
   confirms one article H1 and three TL;DR `li` children, with the hero later.

## Tests / Validation

- Extend `tests/unit/publisher/test_public_document_assembly_u144.py`,
  `test_public_document_types_u144.py`,
  `test_public_document_incident_chain_u144.py`,
  `test_reader_format.py` and `test_reader_format_reflow_u71.py`.
- Add `tests/unit/publisher/test_canonical_preamble_u154.py` for sealed
  Markdown and artifact membership, and
  `tests/integration/test_canonical_preamble_html_u154.py` using the existing
  Markdown dependency and stdlib `html.parser` for article-only H1/list/image
  order checks. No new browser dependency.
- Local gate: `uv run --extra dev --extra docs pytest tests/unit/publisher/test_canonical_preamble_u154.py tests/unit/publisher/test_public_document_assembly_u144.py tests/unit/publisher/test_public_document_types_u144.py tests/unit/publisher/test_public_document_incident_chain_u144.py tests/unit/publisher/test_reader_format.py tests/unit/publisher/test_reader_format_reflow_u71.py tests/integration/test_canonical_preamble_html_u154.py -q`;
  scoped Ruff/check+format and `uv run --extra dev mypy src`.
- During implementation, run `uv run --extra docs mkdocs build --strict`
  because the producer changes publicly rendered Markdown structure. This
  docs-only planning registration itself does not require a site build.

## Non-Goals

No public replay, Pages deployment, Telegram sending, CSS redesign, archive
backfill, numeric/trust-policy changes or duplicate quality-status schema.
