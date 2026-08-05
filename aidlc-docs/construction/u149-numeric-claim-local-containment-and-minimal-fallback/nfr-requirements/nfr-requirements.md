# u149 NFR Requirements — Numeric Containment

**Date**: 2026-08-05
**Status**: Approved for construction by the user's instruction to continue development without approval pauses
**NFR Design decision**: SKIP — implementation stays inside the existing synchronous, pure u144 lifecycle and adds no dependency, infrastructure, async boundary, secret, or external service.

## Reliability and determinism

- **NFR-149.1**: Equal briefing/context inputs produce byte-equal Markdown, equal state, equal ordered witnesses, and equal digests.
- **NFR-149.2**: Each target region receives at most one operation based on original region bytes. Repeated finalization is idempotent.
- **NFR-149.3**: The neutral minimal builder is called at most once per segment per bundle, including survivor fixed-point reruns.
- **NFR-149.4**: Terminal validation is read-only and reruns all hard gates after every local or minimal candidate.
- **NFR-149.5**: A minimal failure cannot recurse; it yields `numeric.fallback_exhausted` and the actual bounded terminal codes.

## Safety and isolation

- **NFR-149.6**: No arbitrary number-token substitution is reachable. Typed correction requires an existing trusted whole-block renderer.
- **NFR-149.7**: Bytes outside targeted owned regions are identical. Optional omission promotes no staged artifact; minimal fallback promotes none for that segment.
- **NFR-149.8**: Numeric recovery is domestic-only. US/crypto retain byte/state compatibility.
- **NFR-149.9**: Any original non-numeric hard code makes fallback ineligible, preventing compliance/entity/disclaimer/structure masking.
- **NFR-149.10**: Seal verification, exact-byte write, rollback boundary, notifier DTO type boundary, and E1/E5/E6 artifact chain remain unchanged.

## Performance

- **NFR-149.11**: Local containment is linear in Markdown bytes plus findings/regions and performs no network, disk, subprocess, or LLM call.
- **NFR-149.12**: The minimal builder and fallback-attempt transition occur at most once per segment. The stored source may be re-finalized once per bounded survivor pass without rebuilding; the enclosing fixed point remains capped by the expected-segment count plus one minimal transition per segment. No unbounded retry loop is allowed.
- **Benchmark observation**: Record local planning/transform and neutral-builder timing on the repository incident fixture without a flaky hard threshold. The enforceable gates are linear traversal, zero I/O/LLM/network calls, bounded call counts, and the existing NFR-001 ten-minute workflow budget.

## Security and diagnostics

- **NFR-149.13**: `claim_digest` is exactly lowercase SHA-256. Logs expose at most its first 16 characters.
- **NFR-149.14**: Logs, GitHub summaries, quality history, and exceptions omit original sentence/Markdown, raw payload, source URL, env, header, cookie, and secret.
- **NFR-149.15**: Witness identifiers and issue codes use existing bounded identifier/code validators and canonical sorted ordering.

## Measurable acceptance checks

1. Property tests cover deterministic offsets, non-overlap, descending edit composition, and repeat equality.
2. Masking fixtures cover numeric+entity, numeric+compliance, numeric+disclaimer, and numeric+required-structure. Indexable layouts retain all applicable codes; pre-layout/non-indexable structure failures prove fallback was never invoked and retain the original structure code.
3. Structural fixtures cover table row, H3 subtree, optional supplement, protected region, malformed ownership, residual scan, and minimal exhaustion.
4. Architecture tests prove publisher does not import `investo.briefing`, finalizer calls the neutral builder at most through its bundle ledger, and no `FinalizedPublicDocument` consumer mutates Markdown.
5. Model tests prove legacy defaults, invalid state/witness combinations, digest validation, and serialization round trips.
6. Full Ruff, format, strict mypy, pytest, no-paid-API, strict MkDocs, and diff checks pass before closeout.
