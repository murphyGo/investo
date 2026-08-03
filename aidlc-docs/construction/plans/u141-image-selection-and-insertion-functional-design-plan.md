# Functional Design Plan: `u141 image-selection-and-insertion`

**Date**: 2026-08-03
**Status**: Approved for construction by the user's instruction to strengthen U-141 as a "final-body-centered semantic selection" contract

## Design objective

Replace source-pool keyword matching with a deterministic contract whose only semantic input is the reader-facing briefing body immediately before public-document finalization. Image metadata identifies candidates; it does not establish editorial relevance by itself.

## Decisions fixed before code generation

1. The selection snapshot is the generated briefing body after narrative generation and before visual/card supplements. It excludes raw routed items, source metadata, and previously inserted visual blocks.
2. Hero relevance is limited to the conclusion, key drivers, and the first story in `## ② 전일 핵심 이슈`. A metadata link card may use the whole `## ②` section.
3. Feed candidates match only when their exact `item_url` is present in the applicable body scope. Title-only fuzzy matching is excluded from v1.
4. Person portraits require an exact named-person alias in the hero scope. Role or institution terms such as `FOMC`, `Fed Chair`, `연준 의장`, `President`, or `White House` cannot select a specific person's portrait.
5. Cleared stored images may become hero assets only when rights-file truth, binary/sidecar pairing, and minimum `600x338` metadata all pass. Metadata-only candidates remain text-only link cards.
6. The observed recurrence rate is 42/748 unique candidates (5.6%), below the planned 10% threshold, so `seen_count` is not a v1 ranking key. Narrative occurrence, `first_seen`, and `candidate_id` define deterministic order.
7. Candidate selection, copy, and card insertion are failure-isolated. An error falls through to curated, AI, data-confidence, or no-card behavior without failing publication.

## Deliverables

- `functional-design/business-logic-model.md`
- `functional-design/business-rules.md`
- `functional-design/domain-entities.md`
- updated U-141 code-generation plan and AIDLC state
- implementation, regression/property tests, and operator documentation

## Explicit non-goals

- semantic embeddings, model calls, perceptual image similarity, or network enrichment
- selecting from raw source volume or popularity/recurrence alone
- auto-clearing rights, hotlinking metadata-only images, or changing Telegram delivery
- deriving a current office holder from a role keyword

## Validation strategy

- Unit tests pin body-scope extraction, exact URL linkage, person-identity matching, deterministic ranking, dimensions/rights gates, and idempotent card insertion.
- Hypothesis tests cover deterministic pure selection/context functions and supplement round trips.
- Pipeline tests pin image-stage ordering and three-segment failure isolation.
- Repository gates cover Ruff, strict mypy, pytest, no-paid APIs, image store, curated assets, and strict MkDocs.
