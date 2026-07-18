# u137 Image Candidate Registry and Licensed Store

## Status

Code Generation complete (7/7, 2026-07-18). Cross-check complete
(2026-07-19, **PASS-with-notes**):
`docs/cross-checks/2026-07-19-u137-image-candidate-registry-and-licensed-store.md`.

## Stage Decision

Functional Design **REQUIRED (lightweight)** and NFR Requirements
**REQUIRED (focused)** — both authored at Step 0 and binding throughout:
R1-R10 / E1-E5 / I1-I17 (`functional-design/`), AC-1.1..AC-1.3 +
TS-1..TS-4 (`nfr-requirements/`). Binding legal posture (R1): metadata
for everything, binaries only with per-item operator clearance.

## Delivered Scope

| Step | Commit | Delivered |
|------|--------|-----------|
| 0 | `e93e7f0` | FD 3 docs + NFR 2 docs; R/E/I/AC/TS ids fixed before development. |
| 1 | `37b3c64` | `visuals/image_library.py`: `ImageCandidateRecord` + `append_candidates` — date ledgers `archive/_meta/image_candidates/{YYYY}/{YYYY-MM-DD}.jsonl`, R3 union merge-rewrite, existing-row-wins, byte-idempotent, `collected_on` = target date (no wall clock). I2/R4 divergence ratified (below). |
| 2 | `ca17a58` | `update_index`: recurrence index with `seen_count` = distinct ledger dates (R5); operator-file rights mirror `metadata-only`/`cleared`/`blocked` (I7 blocked-wins, I8 fail-closed invalid clearance, I14 no auto-promote); atomic rewrite. |
| 3 | `0af9c7a` | `fetch_cleared_candidates`: I13 quadruple gate (`cleared` + env opt-in + `assert_external_asset_allowed` + host allowlist) with I9 clearance URL-identity hash re-verification against file truth; content-addressed store `assets/images/{cid[:2]}/{cid}{ext}` + `.provenance.json` sidecars carrying `content_sha256` (I10 skip-if-present, I11 signature/byte-cap reuse). TS-2 divergence ratified (below). |
| 4 | `54188c4` | Failure-isolated post-routing orchestrator stage: any stage exception → WARN + coverage note, 3-segment publish proceeds; outputs join publish git-add staging. Rollback-exclusion divergence ratified (below). |
| 5 | `68dd5e1` | `scripts/check_image_store.py` CI gate (pair completeness both directions, sha/cid recompute, clearance validity incl. I9, 2 MB / 50 MB budgets, R13 scan, unparseable clearance RED even without a binary, empty store green) wired into `.github/workflows/quality.yml`. Ops finding: `check_curated_assets.py` unwired → DEBT-083. |
| 6 | `1b3cdf3` | CONTRIBUTING operator clearance runbook (binding legal bar: 재게시 가능 근거가 확인된 경우만) with a byte-exact worked example + full gate. |
| closure | `ad393f4` | Audit entries, aidlc-state row, DEBT-083/084 registration. |

## Ratified Divergences (all audit-logged 2026-07-18, cross-check verified consistent)

1. **Step 1 — I2/R4 sanitization split**: u27 STRICT sanitizer would
   rewrite 64-hex/query-string/long-URL content and break I1/I9 hash
   identity, so `candidate_id` is regex-locked (`^[0-9a-f]{64}$`) and
   URL fields are fail-closed secret-screened (`SECRET_ENV_VARS` +
   `scan_for_leak`, any hit drops the whole candidate); free-text fields
   keep the STRICT chokepoint + 160-char title cap. Regression-pinned.
2. **Step 3 — TS-2 digest exemption**: `VisualProvenanceManifest.
   additional_metadata` passes exactly `candidate_id`/`content_sha256`
   verbatim iff the value fullmatches `^[0-9a-f]{64}$`; everything else
   keeps STRICT; u27 catalogue untouched. Shape-lock regression-pinned.
3. **Step 4 — rollback exclusion**: image outputs join the publish
   git-add list but are excluded from rollback snapshots
   (`previous_bytes=None` rollback would delete pre-existing
   merge-rewrite ledgers → R3 never-drop violation). Consistent and
   documented, but the exclusion itself is **not regression-pinned** —
   cross-check M1 → **DEBT-085**.

## Acceptance Criteria (cross-check verified)

| Criterion | Status |
|-----------|--------|
| AC-137.1 — image-bearing run leaves date ledger + updated index | Complete (segmented mode only — cross-check L3; production always segmented) |
| AC-137.2 — binaries only under cleared+env+policy; default run stores 0 | Complete |
| AC-137.3 — every store binary has sidecar + clearance; CI-enforced | Complete |
| AC-137.4 — image-stage failure never fails briefing/publish | Complete (unit + integration pinned) |
| AC-137.5 — 2 MB / 50 MB budgets + R13 gate-enforced | Complete |
| AC-137.6 — multi-day recurrence queryable via `seen_count` | Complete |
| NFR AC-1.1 — storage budget, blocking at fetch + CI | Complete (gate does not re-enforce the 100 B floor — cross-check L2) |
| NFR AC-1.2 — license-compliance blocking CI gate | Complete |
| NFR AC-1.3 — R13 hygiene across persisted artifacts | Complete (gate pre-mask breadth — cross-check M2 → DEBT-086) |

## Final Quality Gate

Step 6 full gate green: ruff / `mypy --strict` (229 files) / pytest
3460 passed (only the pre-existing DEBT-081 pair excepted) /
`scripts/check_no_paid_apis.py` / `scripts/check_image_store.py` /
`mkdocs build --strict` at clean tree. Cross-check re-verification at
worktree HEAD (2026-07-19): u137 unit scope 80 passed, integration
pipeline 9 passed, both guard scripts exit 0, scoped mypy clean.

## TECH-DEBT

- **DEBT-083** — `check_curated_assets.py` unwired (Step 5 ops finding).
  **Resolved 2026-07-19**: curated-assets gate wired into
  `.github/workflows/quality.yml` adjacent to the u137 image-store gate.
- **DEBT-084** — archive-side wall-clock `generated_at` vs u137
  no-wall-clock store (determinism-convention contrast, Low).
- **DEBT-085** (from cross-check M1, Medium) — regression-pin the Step 4
  rollback exclusion.
- **DEBT-086** (from cross-check M2, Medium) — key-scope the
  `check_image_store.py` R13 pre-mask.

## Cross-Check

Verdict **PASS-with-notes** — 6/6 unit AC + 3/3 NFR AC Complete; no
Critical/High; 2 Medium test/scope gaps (M1 → DEBT-085, M2 → DEBT-086);
4 Low (L1 TS-3/R10 wording and L4 BLM §3 gate order fixed 2026-07-19
with edit notes; L2 100 B gate floor and L3 segmented-mode-only stage
recorded in the report). Report:
`docs/cross-checks/2026-07-19-u137-image-candidate-registry-and-licensed-store.md`.

## Deferred (unchanged from plan)

CNBC/Nasdaq og:image enrichment; Reddit community adapter (unauth JSON
blocked, probed 2026-07-17); perceptual-hash dedup; usage phase
(hero/link-card selection, Telegram sendPhoto) — registered when
collection accumulates data.
