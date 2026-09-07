# u150 Terminal Markdown Link Containment

## Status

Code Generation Steps 0-6 and exact-date production qualification are complete
as of 2026-09-07. The reviewed implementation was committed as `e867b0f`,
pushed to the feature branch and `main`, and qualified through the approved
2026-08-27 and 2026-08-28 replays.

## Delivered boundary

u150 extends the existing u112 scanner and u144 finalizer without adding a
second parser or finalization path:

- `_internal.surface_quality` classifies the two canonical link issue codes
  into six closed shapes and performs exact-span, target-removing transforms;
- `_public_document_policy` resolves every link code, shape, and all 16 public
  block kinds through one exhaustive table;
- `public_document` groups findings by owned region, selects one strongest
  action before mutation, and runs the complete terminal gate read-only;
- actionable link residue adds only `document.fallback_exhausted` plus exact
  link codes, while protected and simultaneous hard failures retain their
  original codes;
- sealed documents, staged artifacts, survivor publication, Telegram, Pages,
  and exit status continue to use the u144/u149 contracts.

## Construction summary

| Step | Delivered |
| --- | --- |
| 1 | Redacted six-run incident metadata, six private synthetic link-shape fixtures, and the pre-u150 behavior characterization. |
| 2 | `SurfaceLinkShape`, compatible scanner findings, stable per-occurrence classification, pure target removal, protected-byte behavior, examples, and partial PBT. |
| 3 | Exhaustive shape-aware 16-block policy, one strongest action per region, existing fallback reuse, and required/sibling/artifact/seal preservation. |
| 4 | Bounded actionable-residual diagnostics, exhaustive simultaneous hard gates, and R13 negative coverage over logs, outcomes, summaries, and exceptions. |
| 5 | Pipeline and integration coverage for link-only 3/3 success, genuine partial exit 2, US/crypto numeric fail-close, sealed Telegram inputs, Pages sequencing, and `finalized_degraded` output counts. |
| 6 | Full repository quality gates, u144 supersession notes, DESIGN/component synchronization, cross-check, delivery, and paired exact-date production qualification. |

## Fixed contracts

- Scanner ownership remains in `src/investo/_internal/surface_quality.py`; the
  finalizer receives a closed shape and never parses or resolves a target.
- Recoverable inline/image/incomplete forms retain only proven reader-visible
  label or escaped alt bytes. Target-only autolinks disappear. No target is
  guessed, fetched, completed, archived, or logged.
- Reference definitions and residual unmatched fragments use the region's
  existing replacement/omission owner or fail closed when the region is
  protected, unowned, or unmapped.
- Every affected region receives exactly one strongest action from original
  bytes. No repair-then-replace, retry, global link pass, or post-seal mutation
  is allowed.
- Numeric, entity, compliance, summary, disclaimer, structure, notification,
  seal, and security gates remain authoritative. u149 alone owns domestic
  `finalized_degraded`; US and crypto numeric findings remain trust-blocking.
- Markdown code spans are masked without crossing verified table, list,
  blockquote, fence, details, heading, setext, or thematic block boundaries.
  Balanced labels/targets, escaped angle closers, optional titles, mixed-case
  autolinks, and protected table/details/disclaimer links retain one canonical
  owner and fail closed when exact transformation is ambiguous.
- When a link makes an earlier presentation owner defer its work, the same E3
  region action removes the target first and then reapplies the existing u71
  snippet bound, u61 summary repair, or eligible u76 meaning bound/dedupe. A
  no-op target transform records no false successful outcome.
- Failure surfaces retain only date, segment, phase, and canonical codes. They
  exclude target/evidence text, URLs, Markdown, shapes, region IDs, payloads,
  and secrets.

## Quality evidence

- Focused Step 5 finalizer/orchestrator/integration contract: 9 passed.
- Broad Step 5 internal/publisher/orchestrator/integration scope: 1,350 passed.
- Step 6 focused cumulative regression scope: **346 passed**.
- Step 6 final integrated-SHA pytest: **4,516 passed in 305.48 seconds**.
- `uv lock --check`: passed with 65 resolved packages and no lock drift.
- Ruff lint and format: 576 Python files passed.
- Strict mypy: 254 source files passed.
- Anthropic SDK, paid API, curated-assets, and image-store guards passed.
- Strict MkDocs on Material 9.7.6 and the CSS/built-HTML theme contract passed.
- `git diff --check` passed; tests left no tracked `archive/` or `site_docs/`
  residue.
- The separate cumulative fresh-eyes review approved the final diff with no
  remaining Critical, High, or Medium finding; its independent final scope
  passed 289 tests plus Ruff, mypy, and diff integrity.

## Production qualification

The approved cumulative implementation was pushed to `main` at `e867b0f`.
Both exact-date runs completed with workflow success and exit 0; every segment
logged `state=finalized codes=none`, published its archive path, and produced
two Telegram `HTTP/1.1 200 OK` responses (briefing plus operator surface).

| Target date | Daily workflow | Archive commit | Pages workflow | Telegram | Three live HTTP 200 | Invalid target absent |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-08-27 | `34072608117` success, exit 0, 3/3 finalized | `b949c54` | `34073340478` success | 2 × HTTP 200 | 3/3 | canonical scan 0/3 documents |
| 2026-08-28 | `34074873175` success, exit 0, 3/3 finalized | `02607d3` | `34075738426` success | 2 × HTTP 200 | 3/3 | canonical scan 0/3 documents |

Live paths for both dates were checked under `archive/domestic-equity`,
`archive/us-equity`, and `archive/crypto` at
`https://murphygo.github.io/investo/`. The canonical scanner reported zero
surface issues and zero `markdown.href_ellipsis`/`markdown.unmatched_link`
issues in all six committed Markdown documents. Fixture and PBT coverage
remains the deterministic malformed-target branch proof; unrelated hard gates
remain fail-closed.

## Scope and debt

No dependency, source, secret, environment flag, prompt, retry, persistence
schema, public fallback copy, or infrastructure component was added. No new
TECH-DEBT or ADR is required. Existing DEBT-090 continues to track the separate
daily-pipeline wall-clock target.
