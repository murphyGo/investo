# Cross-Check: u137 image-candidate-registry-and-licensed-store

**Scope**: u137 image-candidate-registry-and-licensed-store
**Date**: 2026-07-19
**Checked by**: investo-qa
**Implementation commits**: `e93e7f0` (FD/NFR), `37b3c64`, `ca17a58`, `0af9c7a`, `54188c4`, `68dd5e1`, `1b3cdf3`; closure `ad393f4`

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| Complete | 9 | 100% |
| Partial | 0 | 0% |
| Gap | 0 | 0% |
| Deferred | 0 | 0% |
| In Progress | 0 | 0% |
| **Total** | **9** | **100%** |

Total = 6 unit-level AC (AC-137.1..AC-137.6) + 3 NFR AC (AC-1.1..AC-1.3).

**Overall Compliance**: 100% (all AC Complete)

**QA Verdict**: **PASS-with-notes** (no Critical/High; 2 Medium test/scope gaps, 4 Low)

## Scope

u137 persists u136-harvested image references into a metadata-only-by-default candidate registry (date ledgers + recurrence index), an operator-file-driven rights state machine, a quadruple-gated content-addressed licensed store, a failure-isolated orchestrator stage, and a CI license/budget/R13 gate. Acceptance surface: the plan's AC-137.1..AC-137.6, the unit NFR AC-1.1..AC-1.3, FD contracts R1-R10 / E1-E5 / I1-I17, TS-1..TS-4, and the three ratified divergences.

## Acceptance Criteria (unit-level)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| AC-137.1 — image-bearing run leaves date ledger + updated index | Complete | `src/investo/visuals/image_library.py:252-321` (merge-rewrite), `478-560` (index rebuild); stage sequence `src/investo/orchestrator/pipeline.py:870-940`, wired at `2652-2666`. Integration pin: `tests/integration/test_pipeline.py:377-434` (ledger + `index.json` exist and both join the git add list). Note: stage runs in segmented mode only — see L3. |
| AC-137.2 — binaries only under cleared+env+policy; default run stores 0 | Complete | Quadruple gate `image_library.py:710-863` (env short-circuit `746-760`; blocked file-truth `773-776`; clearance re-validation `777-781`; policy/host `793-801`). Pins: `tests/unit/visuals/test_image_library.py:751-764` (env off, fail-client), `767-793` (metadata-only never fetches in any combination), `795-814` (blocked wins over valid manifest AND stale-cleared index), `817-835` (host allowlist blocks pre-request), `838-861` (I9 mismatch at fetch time). |
| AC-137.3 — every store binary has sidecar + clearance; CI-enforced | Complete | Sidecar write `image_library.py:824-849` (`content_sha256` + `candidate_id` in `additional_metadata`); gate `scripts/check_image_store.py:107-128` (pairing both directions), `148-170` (sha + cid recompute), `173-202` (clearance validity incl. I9). Pins: `tests/unit/visuals/test_check_image_store.py:193-227`; clean store built by the REAL fetch machinery passes (`179-185`). |
| AC-137.4 — image-stage failure never fails briefing/publish | Complete | `pipeline.py:932-940` (catch-all → WARN + `failed: <Type>` note); unit pin `tests/unit/orchestrator/test_image_candidate_stage.py:86-109`; integration pin `tests/integration/test_pipeline.py:314-374` (forced `append_candidates` crash → SUCCESS, 3 segments published, git add/commit/push, no operator alert). Note rides the daily coverage line (`orchestrator/source_health.py:60,98-99`; `pipeline.py:3049-3063`). |
| AC-137.5 — 2 MB / 50 MB budgets + R13 gate-enforced | Complete | Fetch-side cap reused (`external_image.py:146-147`, over-cap test `test_image_library.py:911-928`); gate per-file `check_image_store.py:110-114` + total `130-134` (imports `_MAX_IMAGE_BYTES`, not re-declared), R13 scan `205-229`; pins `test_check_image_store.py:230-248, 279-293`. Wired: `.github/workflows/quality.yml:61-66`. |
| AC-137.6 — multi-day recurrence queryable via `seen_count` | Complete | `image_library.py:498-535` (`seen_count` = len(distinct ledger dates)); pin `test_image_library.py:519-537` (3-date/2-source candidate → seen_count 3, sorted source union, first/last span). |

## NFR Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| AC-1.1 — storage budget, blocking at fetch + CI | Complete | Both enforcement points pinned (over-cap fetch body rejected: `test_image_library.py:911-928`; gate per-file + shrunken-total-budget fixture RED: `test_check_image_store.py:230-248`); sidecar JSON counts toward total (`check_image_store.py:92-96`); `.png`/`.jpg`-only store (`:99-105`). Note: gate does not re-enforce the 100 B floor — see L2. |
| AC-1.2 — license-compliance blocking CI gate | Complete | Every listed RED class has a distinct-message test; all three binding green states pinned (`test_check_image_store.py:151-185`); committed-repo subprocess run passes (`:140-148`); wired in `quality.yml:61-66`. |
| AC-1.3 — R13 hygiene across persisted artifacts | Complete | Pinned Telegram-token-in-title redaction test (`test_image_library.py:289-298`), live-env-secret scrub (`:301-309`), gate-level PAT-in-ledger RED naming the pattern not the value (`test_check_image_store.py:279-293`). See M2 for gate-scan breadth. |

## Ratified Divergence Verification

| Divergence | Consistent? | Regression-pinned? |
|------------|-------------|--------------------|
| Step 1 — I2/R4 sanitization split | Yes (`image_library.py:174, 212-221, 202-210, 338-346, 383-396, 186-200`; audit + docstring + plan all match) | Yes: `test_record_rejects_mismatched_candidate_id` (`:117-129`), `test_url_carrying_env_secret_drops_candidate_entirely` (`:342-357`), `test_real_feed_shaped_urls_pass_screening` (`:360-383`), plus the two chokepoint redaction tests. |
| Step 3 — TS-2 digest exemption | Yes (`provenance.py:121-124, 155-167`; u27 catalogue untouched) | Yes: `test_digest_metadata_exemption_is_shape_locked` (`test_image_library.py:965-994`) + `test_r13_scan_tolerates_bare_hex_digests` (`test_check_image_store.py:296-305`). |
| Step 4 — rollback exclusion | Yes (`pipeline.py:1563-1575` join commit list only, never snapshots `:1216-1219`; rationale `:1155-1162` matches audit) | **Partially — see M1.** Staging join and failure isolation pinned; the exclusion itself has no test. |

## Findings

### Critical / High

None.

### Medium

**M1. Rollback-exclusion divergence is documented but not regression-pinned** — `src/investo/orchestrator/pipeline.py:1155-1162, 1216-1219`. No test injects a publish write-failure on a run whose image stage wrote (or merged into a pre-existing) ledger and asserts the ledger/index survive `_rollback_paths`. A future edit registering `extra_commit_paths` with `previous_bytes=None` (the `asset_paths` idiom at `:1219`) would reintroduce exactly the R3 never-drop violation — and nothing would go red. Existing rollback tests (`tests/unit/orchestrator/test_run_pipeline.py:1478-1523`) use imageless items. Fix: extend the `PublisherIOError` rollback test with one image-bearing item and a pre-seeded ledger; assert ledger bytes intact post-rollback. Effort ~30-45 min. → Registered as **DEBT-085**.

**M2. CI-gate R13 pre-mask is shape-locked but not key-scoped** — `scripts/check_image_store.py:75, 223` strips every bare `\b[0-9a-f]{64}\b` token from the full text of every scanned artifact before `scan_for_leak`. The ratified TS-2 exemption is key-scoped to `additional_metadata.candidate_id`/`content_sha256` (the runtime side honors that — `provenance.py:155-167`); the gate widens it file-wide. Consequence: a 64-hex-shaped secret anywhere in a scanned file evades the gate. Residual exposure: operator-authored clearance manifests, whose `ExternalAssetManifest` fields carry no sanitizer (`policy.py:55-66`) and for which the gate is the only automated check. Fix: JSON-aware masking (mask only `candidate_id`/`content_sha256` values, index map keys, ledger `candidate_id` fields). Effort ~1-2 h. → Registered as **DEBT-086**.

### Low

**L1. FD R10 / TS-3 "stdlib-only" wording diverges from the shipped gate** — `check_image_store.py:51-57` imports pydantic + four in-tree investo modules (docstring acknowledges). Substantive constraint (zero NEW dependencies) holds; mirror precedent `check_curated_assets.py` does the same. Suggest amending R10/TS-3 wording ("no new dependency; may reuse in-tree modules") rather than changing code. → **Done 2026-07-19**: R10/TS-3 amended with edit notes.

**L2. Gate does not enforce the 100 B per-file floor** — NFR AC-1.1 says the 100-byte minimum carries over but the gate checks only over-cap (`check_image_store.py:110-114`); the floor binds at fetch time only (`external_image.py:147`). Trivial to add. Recorded here; fold into the DEBT-086 gate pass when that is worked.

**L3. Image stage is segmented-mode-only** — `pipeline.py:2628-2666` (`segmented_mode = generate is None`, `:2510`). Production always runs segmented so AC-137.1 is met for every real run; the legacy injected-generate path silently skips the stage. Recorded here per QA recommendation.

**L4. BLM §3 pseudocode orders gates (3)/(4) before skip-if-present; implementation checks skip-if-present first** — `image_library.py:784-801` vs `business-logic-model.md:70-72`. No invariant impact; counter semantics differ marginally (`gate_blocked` not incremented for already-stored candidates). → **Done 2026-07-19**: BLM §3 aligned to the implementation with an edit note.

## Verified Clean

- Module boundary: `image_library.py` imports only models, `_internal`, sibling visuals (`:105-123`); sole importer `orchestrator/pipeline.py:242`.
- No Anthropic SDK, no paid API, no new endpoint; `check_no_paid_apis.py` exit 0.
- Zero new unconditional HTTP call sites; env short-circuit pinned by fail-on-request transports across the gate matrix.
- I14 read-only clearances (byte-identity pinned); `EXTERNAL_IMAGE_SCRAPING_ENABLED` default untouched.
- No wall clock in persisted values; DEBT-084 correctly captures the pre-existing archive-side contrast.
- Determinism/idempotency all pinned (byte-idempotent ledger, atomic writes, deterministic index, refresh-to-empty).
- Path/contract consistency across library/pipeline/gate/runbook; runbook worked-example candidate id recomputed and verified byte-exact (`4b71cff1…f377d9`).
- u136↔u137 field mapping consistent (caps 1000/240 both sides; int width/height with bool exclusion; absent key → None).
- Both hex-digest exemptions shape-locked; runtime one additionally key-scoped (gate breadth = M2).
- DEBT-083 (since resolved by wiring), DEBT-084 registered; aidlc-state u136/u137 rows and all four audit entries match implementation.

## Verification

- Cross-check executed at worktree HEAD on 2026-07-19; all tests run, not inferred.
- u137 unit scope: 80 passed.
- `tests/integration/test_pipeline.py`: 9 passed.
- `scripts/check_image_store.py`: exit 0.
- `scripts/check_no_paid_apis.py`: exit 0.
- Scoped mypy: clean.

## Proposed Actions

- Register M1 as a Medium TECH-DEBT item. — **Done 2026-07-19**: DEBT-085.
- Register M2 as a TECH-DEBT item (QA band: Medium-Low). — **Done 2026-07-19**: DEBT-086 (triaged Medium, low edge).
- Extend DEBT-082 with the u136 L1 `_URL_MAX_LEN`/`_IMAGE_URL_MAX` duplication. — **Done 2026-07-19**.
- Amend R10/TS-3 wording (L1) and align BLM §3 (L4). — **Done 2026-07-19** with edit notes in the u137 FD/NFR docs.
- Mark the u137 cross-check complete in `aidlc-docs/aidlc-state.md`.
