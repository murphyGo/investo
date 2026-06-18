# Code Generation Plan: `u101 verified-fact-cache-and-entity-guard`

**Date**: 2026-06-18
**Unit**: u101 verified-fact-cache-and-entity-guard
**Stage**: Code Generation
**Status**: Complete
**Source**: User-reported generated-briefing defect: 2026-06-16 US-equity briefing described the 2026-06-17 FOMC press conference as a Powell press conference after the Fed chair had changed to Kevin Warsh.
**Estimated Effort**: ~6-9 h
**Dependencies**:
- u35/u43 event lookahead and `fomc-calendar`
- u55 numeric-freshness-and-market-fact-gates for trust-gate style
- u59 macro-actual-priority-and-lineage for source-backed macro-event lineage patterns
- u85 unified-validator-gate-protocol for publish-boundary validator style
- u100 surface-quality-gate for final first-viewport blocking behavior

---

## Problem Statement

The current pipeline can collect the official Federal Reserve FOMC calendar and render a forward-looking `FOMC Press Conference` item. That calendar event does not carry the current Fed chair name. In `archive/us-equity/2026/06/2026-06-16.md` on `origin/main`, Stage 2 filled that missing person name as `파월 의장 기자회견` in the first viewport and §④, while the same run's domestic segment had a source-backed Yonhap item saying `케빈 워시 연방준비제도 의장의 첫 FOMC`.

This is a high-trust defect because readers treat officeholder names as factual, not narrative flavor. A hard-coded fix such as `current_fed_chair = Kevin Warsh` would only move the failure to the next leadership transition. The implementation must make high-drift entity facts refresh from source-of-record pages and must fail closed when the fact is not fresh.

## Goal

Create a small verified fact subsystem for high-drift entity facts. The first shipped fact is `fed.current_chair`, sourced from the Federal Reserve Board Members page. The fact is injected into briefing generation as structured context and enforced at publish time so current-role claims cannot contradict fresh official data or rely on stale cache.

The reader outcome is:
- When the Fed chair fact is fresh, FOMC prose may say `Kevin Warsh 의장`.
- When the fact is missing, failed, or expired, FOMC prose may say only `FOMC 기자회견` or `연준 기자회견`.
- When generated markdown says `파월 의장` for a target-date-current FOMC event while the fresh fact says Kevin Warsh, publish is blocked.

## Existing Coverage / Deduplication

- u35/u43 already collect forward FOMC events. They do not know the current chair and must not guess it.
- u59 handles macro event priority, actuals, and lineage. It does not maintain current officeholder state.
- u55/u70 verify numeric and market anchor facts. This unit is explicitly non-numeric and should not edit `CoreFact`.
- u57/u60 handle shared macro evidence matching. They do not validate person-role claims.
- u100 repairs and blocks surface artifacts. This unit blocks semantic entity-role contradictions and should run through a dedicated publisher guard.
- u86 curated assets contains `person:jerome-powell` image matching. That asset selection logic is not a factual authority and must not be used to infer current officeholders.

## Scope Boundary

In scope:
- One model module for fact snapshots and fact bundles.
- One official source adapter: Federal Reserve Board Members page to populate `fed.current_chair`.
- One prompt context renderer for verified current facts.
- One publish-boundary guard for Fed chair role/name conflicts.
- One append-only operator lineage file under `archive/_meta/fact_snapshots.jsonl`.
- Unit and integration tests using official-source fixtures.

Out of scope:
- SEC chair, US president, ECB/BOJ officials, index constituents, market holidays, or other future fact IDs beyond registry placeholders.
- Broad web search, third-party knowledge graphs, Wikipedia, LLM-based fact checking, browser scraping, or paid APIs.
- Rewriting historical archive files.
- Replacing `fomc-calendar`, macro lifecycle, or numeric gates.
- Changing Telegram formatting except through the existing generated markdown summary path.

## Stage Decision

Functional Design: skip. The unit adds a bounded source/model/guard slice that follows existing source adapter, pydantic model, prompt-context, and publisher validator patterns.

NFR Requirements: skip as a separate document. The plan pins the relevant NFR contracts directly: official no-key source, R10 fixture recording, R13-safe diagnostics, fail-closed stale handling, and deterministic publish blocking.

## Implementation Steps

- [x] Step 1 - Add fact models.
  - Create `src/investo/models/facts.py`.
  - Define:
    - `FactId = Literal["fed.current_chair"]`.
    - `FactStatus = Literal["fresh", "stale", "missing", "failed"]`.
    - `FactSourceTier = Literal["S", "A", "B", "C"]`.
    - `FactSnapshot` as frozen pydantic v2 model with `extra="forbid"` and fields:
      - `fact_id: FactId`
      - `value: str`
      - `label_ko: str | None`
      - `aliases: tuple[str, ...]`
      - `role: str`
      - `source_name: str`
      - `source_url: str`
      - `source_tier: FactSourceTier`
      - `observed_at: datetime`
      - `expires_at: datetime`
      - `status: FactStatus`
      - `raw_evidence_label: str`
    - `VerifiedFactBundle` with `target_date: date`, `facts: tuple[FactSnapshot, ...]`, and helpers `get(fact_id)`, `fresh(fact_id, now_utc)`.
  - Validation rules:
    - `observed_at` and `expires_at` must be timezone-aware.
    - `expires_at > observed_at`.
    - `value`, `role`, `source_name`, and `source_url` must be non-empty.
    - `raw_evidence_label` must be a short parsed label, not raw HTML.
  - Export public names from `src/investo/models/__init__.py` only if the repo already exports similar model groups there; otherwise keep direct imports.

- [x] Step 2 - Add the `fed-board-leadership` source adapter.
  - Create `src/investo/sources/fed_board_leadership.py`.
  - Endpoint: `https://www.federalreserve.gov/aboutthefed/bios/board/default.htm`.
  - Follow existing adapter conventions:
    - `name: ClassVar[str] = "fed-board-leadership"`.
    - Use `retry_get`.
    - Use the standard User-Agent pattern used by existing official adapters.
    - No API key, no cookies, no browser automation.
  - Parse the HTML text using stdlib tools already used in the repo. Use an `HTMLParser` subclass or an existing project helper; do not add BeautifulSoup.
  - Extract anchor/list text labels from the Board Members content.
  - Accept exactly one label matching the shape `<person>, Chairman`.
  - For `Kevin Warsh, Chairman`, emit one `NormalizedItem`:
    - `source_name="fed-board-leadership"`
    - `category="macro"`
    - `title="Current Federal Reserve Chair: Kevin Warsh"`
    - `summary="Kevin Warsh, Chairman"`
    - `url` set to the Board Members URL
    - `published_at` set from the collection window target date at UTC midnight
    - `raw_metadata`:
      - `fact_id="fed.current_chair"`
      - `fact_value="Kevin Warsh"`
      - `fact_label_ko="케빈 워시"`
      - `fact_role="Chairman, Board of Governors of the Federal Reserve System"`
      - `fact_status="fresh"`
      - `fact_source_tier="S"`
      - `fact_expires_at="<observed_at + 24h ISO>"`
      - `raw_evidence_label="Kevin Warsh, Chairman"`
  - Korean label rule for this first slice:
    - `Kevin Warsh` maps to `케빈 워시`.
    - Other values map to `None` unless a local alias table in this adapter explicitly contains them.
    - Do not call an LLM or translation service.
  - If no chairman label exists, return an empty list and let coverage report zero items.
  - If multiple chairman labels exist, raise `SourceFetchError(transient=False)` because ambiguous source-of-record parsing must not silently pick a person.

- [x] Step 3 - Register source and tier.
  - Add the adapter to the source registry in `src/investo/sources/aggregator.py`.
  - Add `"fed-board-leadership": "S"` to `src/investo/sources/tiers.py`.
  - Route it to `us-equity` in `src/investo/briefing/segments.py` using the same official Fed-policy routing family as `fomc-calendar` and `fomc-rss`.
  - Ensure this source does not count as a price source and does not satisfy numeric core anchors.
  - Add a source plugin contract test if `tests/unit/sources/test_plugin_contract.py` enumerates registered source names.

- [x] Step 4 - Build fact bundle extraction.
  - Create `src/investo/briefing/fact_context.py`.
  - Add `build_verified_fact_bundle(items, target_date, now_utc) -> VerifiedFactBundle`.
  - It reads `NormalizedItem.raw_metadata` keys from Step 2 and constructs `FactSnapshot`.
  - It marks a snapshot `stale` when `expires_at <= now_utc`.
  - It marks absent `fed.current_chair` as missing through bundle helper behavior, not by fabricating a dummy fact with a fake value.
  - It deduplicates by `fact_id`; if two fresh values disagree, raise a fact conflict exception defined in this module. The first slice should only have one source, but the conflict path is required so future sources do not silently override.
  - Add `render_fact_context_block(bundle, now_utc) -> str`:
    - Fresh fact output:
      - `## 검증된 현재 팩트`
      - `- fed.current_chair: Kevin Warsh (케빈 워시), Chairman, source=fed-board-leadership, expires=<ISO>`
    - Missing or stale output:
      - `## 검증된 현재 팩트`
      - `- fed.current_chair: unverified; do not name the current Fed chair`
  - Keep the rendered block under 600 characters.

- [x] Step 5 - Inject fact context into Stage 2.
  - Extend `STAGE2_USER_TEMPLATE` in `src/investo/briefing/prompts.py` with `{fact_context}` after lookahead/carryover context and before bundle context.
  - Update the Stage 2 system prompt with a `Verified current facts` rule:
    - Person-role claims for current officeholders must come from `검증된 현재 팩트` or from supplied source items.
    - For FOMC meetings and press conferences, use the `fed.current_chair` value only when fresh.
    - When `fed.current_chair` is unverified, write `FOMC 기자회견` or `연준 기자회견`; do not write Powell, Warsh, or another person name.
    - Historical references must be explicitly marked as former/prior/past and tied to the supplied source item.
  - Update `generate_briefing` signatures through the decomposed briefing pipeline modules to accept `fact_context_block: str = ""`.
  - Keep default behavior byte-compatible when the block is empty.

- [x] Step 6 - Wire fact bundle in orchestrator.
  - In the collect/generate path, build one `VerifiedFactBundle` from all collected items before segment generation.
  - Pass the same rendered fact context block to all segments.
  - Append one JSON line per run to `archive/_meta/fact_snapshots.jsonl` with:
    - `target_date`
    - `observed_at`
    - `facts`
    - `missing_fact_ids`
    - `stale_fact_ids`
    - `conflict_fact_ids`
  - Use existing atomic write or append helpers if present. If no append helper exists, follow existing JSONL append patterns in `quality_history` or macro lifecycle modules.
  - Fact snapshot persistence failure logs a warning and does not stop collection; the guard still uses the in-memory bundle for the current run.

- [x] Step 7 - Add publish-boundary entity fact guard.
  - Create `src/investo/publisher/entity_fact_guard.py`.
  - Define `EntityFactViolation` dataclass and `EntityFactGuardError`.
  - Implement `scan_entity_fact_claims(markdown, bundle, target_date, now_utc) -> tuple[EntityFactViolation, ...]`.
  - First-slice patterns:
    - Current Fed chair claim terms:
      - `파월 의장`
      - `제롬 파월 의장`
      - `Powell chair`
      - `Chair Powell`
      - `Powell press conference`
      - `파월 기자회견`
    - Allowed historical qualifiers in the same sentence:
      - Korean: `전임`, `이전`, `과거`, `전 의장`
      - English: `former`, `prior`, `previous`
    - Allowed when the sentence cites a supplied source item whose title itself contains Powell and does not describe a current target-date event.
  - Blocking rules:
    - If `fed.current_chair` is fresh and `value` is not Powell, block current-role Powell claims unless a historical qualifier is present.
    - If `fed.current_chair` is missing or stale, block all current Fed chair person-name claims for Powell and Warsh unless the sentence has a historical qualifier or the exact person name appears in a same-run source item title for a non-current event.
    - Do not block generic `Federal Reserve`, `연준`, `FOMC`, `chair`, or `의장` without a person name.
  - Diagnostic output must include only segment, fact_id, expected value, offending term, line number, and a bounded 120-character sentence preview passed through existing redaction.

- [x] Step 8 - Wire guard before publish.
  - Add the guard to the post-reader-format publish boundary for each segment.
  - Use the u85 validation registry when it supports this shape; otherwise call the guard directly next to existing publish-boundary checks with a clear comment naming u101.
  - Ensure a guard failure marks the affected segment failed/blocked consistently with `SurfaceQualityError` handling.
  - Partial-publish behavior:
    - If only US equity violates the guard, domestic and crypto segments may publish if their own validations pass.
    - If all enabled segments violate the guard, the pipeline exits failed through the existing all-fail path.

- [x] Step 9 - Tests.
  - Model tests:
    - `FactSnapshot` rejects naive datetimes.
    - `FactSnapshot` rejects `expires_at <= observed_at`.
    - `VerifiedFactBundle.fresh("fed.current_chair", now_utc)` returns the snapshot before expiry and `None` after expiry.
    - Serialization round-trip preserves aliases and timestamps.
  - Source tests:
    - Fixture with `Kevin Warsh, Chairman` emits one item with correct raw metadata.
    - Fixture with no chairman emits zero items.
    - Fixture with two chairman labels raises `SourceFetchError`.
    - Raw HTML is not copied into raw metadata.
  - Prompt tests:
    - Fresh fact block includes `Kevin Warsh` and `fed.current_chair`.
    - Stale/missing block includes `unverified; do not name the current Fed chair`.
    - Stage 2 prompt contains the rule forbidding current-officeholder names unless verified.
  - Publisher guard tests:
    - Fresh Warsh fact blocks `파월 의장 기자회견`.
    - Fresh Warsh fact blocks `Chair Powell press conference`.
    - Fresh Warsh fact allows `전임 의장 Powell`.
    - Stale fact blocks `Kevin Warsh 의장 기자회견` and `파월 의장 기자회견`.
    - Missing fact allows `FOMC 기자회견`.
  - Orchestrator tests:
    - The fact context block is passed to every segment generation call.
    - A US-equity entity guard violation fails only that segment under partial publish.
    - `archive/_meta/fact_snapshots.jsonl` receives one sanitized row per run.

## Acceptance Criteria

1. `fed-board-leadership` is a registered Tier S no-key source and uses only the Federal Reserve Board Members page.
2. Fresh `fed.current_chair` snapshots expire after 24 hours by default and expired values cannot authorize person-name claims.
3. Stage 2 prompt input includes a verified-facts block for all segments in a run.
4. When `fed.current_chair` is missing or stale, generated output is allowed to say `FOMC 기자회견` but not `Kevin Warsh 의장 기자회견` or `파월 의장 기자회견`.
5. When `fed.current_chair` is fresh and not Powell, publish blocks target-date-current `파월 의장` / `Chair Powell` claims.
6. Historical Powell references remain allowed only with former/prior wording in the same sentence.
7. Fact snapshot JSONL and guard diagnostics are sanitized and contain no raw HTML or secret-shaped values.
8. The implementation does not add paid APIs, browser automation, third-party scraping, or a new runtime dependency.

## Tests / Validation

Run these local gates for the implementation slice:

```bash
uv run pytest tests/unit/models/test_facts.py tests/unit/sources/test_fed_board_leadership.py tests/unit/briefing/test_fact_context.py tests/unit/briefing/test_prompts.py tests/unit/publisher/test_entity_fact_guard.py tests/unit/orchestrator/test_fact_context_wiring.py
uv run ruff check src/investo/models/facts.py src/investo/sources/fed_board_leadership.py src/investo/briefing/fact_context.py src/investo/publisher/entity_fact_guard.py tests/unit/models/test_facts.py tests/unit/sources/test_fed_board_leadership.py tests/unit/briefing/test_fact_context.py tests/unit/publisher/test_entity_fact_guard.py tests/unit/orchestrator/test_fact_context_wiring.py
uv run mypy --strict src/investo/models/facts.py src/investo/sources/fed_board_leadership.py src/investo/briefing/fact_context.py src/investo/publisher/entity_fact_guard.py
```

Add `mkdocs build --strict` only when implementation touches docs or public site navigation.

## Non-Goals

- Do not store a permanent hard-coded chair name as the source of truth.
- Do not use stale fact snapshots as truth after expiry.
- Do not add Wikipedia, search APIs, LLM browsing, paid feeds, or browser automation.
- Do not backfill old archives.
- Do not implement non-Fed fact IDs in this unit.
- Do not weaken numeric, compliance, surface-quality, or disclaimer gates.
