# Business Logic Model — `u137 image-candidate-registry-and-licensed-store`

**Date**: 2026-07-18
**Source**: u137-image-candidate-registry-and-licensed-store-code-generation-plan.md

Algorithms + sequence for the image-candidate ledger, recurrence index,
rights state machine, and licensed store. Reuses the existing
`visuals/policy.py` / `visuals/external_image.py` /
`visuals/provenance.py` machinery and `_internal/_io.write_atomic`. Rule
ids (`R1`-`R10`) and entity/invariant ids (`E1`-`E5`, `I1`-`I17`)
reference the sibling FD files; `AC-1.x` references
`nfr-requirements/nfr-requirements.md`.

---

## 1. Candidate extraction + ledger write (run time)

```
append_candidates(target_date, routed_items) -> LedgerWriteReport:
  rows = {}
  for item in routed_items:                       # routing order = deterministic input order
    if "image_url" not in item.raw_metadata: continue        # u136 keys only (R3)
    cid = sha256(normalize(image_url))                       # I1 / R2
    if cid in rows: continue                                 # same-run dedup, first wins (R3)
    rows[cid] = ImageCandidateRecord(                        # E1: frozen, extra=forbid
      candidate_id=cid, image_url=..., source_name=..., segment=...,
      item_url=..., item_title=sanitize+cap160,              # I2 / R4
      image_width/height/mime/credit from u136 keys or None,
      collected_on=target_date)                              # I3 — no wall clock
  existing = parse(ledger_path(target_date)) if exists       # merge-rewrite (R3)
  merged = existing | rows, existing-row-wins per candidate_id
  write_atomic(ledger_path, jsonl(sorted(merged by candidate_id), fixed key order))
  return LedgerWriteReport(new=…, existing=…, skipped=…)     # I4 — byte-idempotent re-run
```

`ledger_path(d) = archive/_meta/image_candidates/{d:%Y}/{d:%Y-%m-%d}.jsonl` (R3).

## 2. Index rebuild + rights mirror (run time)

```
update_index(target_date) -> IndexReport:
  entries = {}
  for ledger_file in all date ledgers:                       # derived-only (I6)
    for row in ledger_file:
      e = entries.setdefault(row.candidate_id, fresh)
      e.first_seen = min(...); e.last_seen = max(...)
      e.seen_count = count of DISTINCT ledger dates          # v1 재출현 signal (R5, AC-137.6)
      e.sources    = sorted unique source_names
  for cid, e in entries:
    e.rights_state = mirror_of_files(cid)                    # I7 — existence only:
      #   clearances/{cid}.blocked present          -> "blocked"   (wins, I7)
      #   clearances/{cid}.manifest.json valid(I8/I9)-> "cleared"
      #   else                                      -> "metadata-only"
  write_atomic(index_path, json(sorted keys, fixed entry key order))   # I5
  return IndexReport(...)
```

Code never writes `clearances/` (I14); an invalid clearance manifest
mirrors as `metadata-only` + WARN (I8, fail-closed).

## 3. Cleared fetch + content-addressed store (run time, quadruple-gated)

```
fetch_cleared_candidates(index, *, client=None) -> FetchReport:
  if not external_image_scraping_enabled(): return zero-fetch report   # gate (2), I13
  for cid in cleared candidates only:                                  # gate (1); blocked/metadata-only never enter
    manifest = parse ExternalAssetManifest(clearances/{cid}.manifest.json)  # E3
    if invalid or sha256(normalize(manifest.source_url)) != cid:       # I8 / I9
      WARN; continue
    if store_binary_path(cid) exists: continue                         # I10 — idempotent skip (precedes gates 3/4)
    assert_external_asset_allowed(manifest, scraping_enabled=env)      # gate (3), I13
    assert_external_image_host_allowed(url, allowed_hosts=env)         # gate (4), I13
    fetched = reuse external_image fetch machinery                     # R8 — minimal publicization
             (signature + 100B-2,000,000B cap via _extension_for_image)  # I11 / AC-1.1
    if fetched is None: WARN; continue                                 # nothing written
    write_atomic_bytes(assets/images/{cid[:2]}/{cid}{ext}, bytes)
    sidecar = build_external_provenance(..., dims via existing reader,
              additional_metadata += {"content_sha256": sha256(bytes)})  # I12
    write_manifest(sidecar, -> {cid}{ext}.provenance.json)             # R8 / TS-2
  return FetchReport(fetched=…, skipped=…, rejected=…)
```

`metadata-only` / `blocked` candidates produce **zero** fetch attempts in
every env/policy combination — regression-pinned (I13, AC-137.2).

*(edited 2026-07-19 — u137 cross-check L4: the I10 skip-if-present check
now precedes policy gates (3)/(4), matching the shipped implementation
(`image_library.py:784-801`); consequence: gate-blocked counters are not
incremented for already-stored candidates. No invariant impact.)*

## 4. Pipeline sequence (one run, failure-isolated stage)

```
orchestrator/pipeline.py — after segment routing (R9):
  try:
    ledger_report = append_candidates(target_date, routed_items)   # §1
    index_report  = update_index(target_date)                      # §2
    fetch_report  = fetch_cleared_candidates(index)                # §3
    stage outputs (ledger, index, binaries, sidecars)
      -> join existing publish staging (git add list)              # R9
    record stage result in run trace
  except Exception:
    WARN + one coverage diagnostic line; pipeline CONTINUES        # I16 / AC-137.4
  -> generate / publish / notify proceed unaffected on every path
```

## 5. CI gate (`scripts/check_image_store.py`, build/CI time)

```
check_image_store():                                # no new third-party deps (in-tree reuse allowed), mirrors check_curated_assets.py (R10, TS-3)
  for binary under assets/images/:
    extension recognized (.png/.jpg)?               else RED
    sidecar {binary}.provenance.json valid?         else RED   (I12)
    clearance manifest exists + valid + I9 hash ok? else RED   (AC-1.2)
    size <= 2,000,000 B?                            else RED   (AC-1.1)
  orphan sidecar (no binary)?                       RED        (I12)
  unparseable clearance manifest (even w/o binary)? RED        (I8, fail-closed)
  store total <= 50,000,000 B?                      else RED   (AC-1.1)
  R13 secret-pattern scan over ledgers/index/manifests: hit -> RED  (AC-1.3)
  exit 0 with summary line otherwise                # empty store = green
```

## 6. Determinism + degradation summary

- Ledger + index are byte-deterministic and re-run idempotent
  (I4/I5/I6); the store is content-addressed and skip-if-present (I10).
- No wall clock in persisted values (`collected_on` = target date, I3);
  provenance sidecars are written once at first store and never churned.
- Rights transitions are operator-file-only (I14); default runs store
  zero binaries (I17/AC-137.2); `blocked` is permanent (I15).
- Every runtime failure in this unit degrades to WARN + diagnostics —
  briefing generation/publish never fails because of images (I16);
  license/budget/secret violations fail **closed** at CI time
  (R10, AC-1.1/AC-1.2/AC-1.3).
