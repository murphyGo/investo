# Code Generation Plan: `u112 reader-markdown-polish-gate-v2`

**Date**: 2026-06-23
**Unit**: u112 reader-markdown-polish-gate-v2
**Stage**: Code Generation
**Status**: Backlog / Planned
**Source**: 2026-06-23 generated-briefing quality review with mobile, Markdown, and data-trust findings
**Estimated Effort**: ~4-6 h
**Dependencies**:
- u51 TLDR block and number bold inversion is complete.
- u61 first-viewport summary gate v2 is complete.
- u71 reader-first-viewport reflow is complete.
- u81 reader-format subpackage is complete.
- u100 surface-quality gate is complete.

---

## Problem Statement

The current surface-quality gate repairs several first-viewport defects, but public markdown still shows remaining polish failures in June 2026 samples: malformed timestamp watermark brackets, broken signed-number emphasis such as `**-**0.04%**p**`, nested bold fragments around signed values, truncated lines ending mid-token, links whose href contains ellipsis, and Korean artifacts such as `민감도을`.

These defects reduce reader trust because they look like failed string processing.

## Goal

Extend deterministic post-render validation so malformed Markdown and truncation artifacts are repaired when the safe repair is fixed, and blocked before archive/index writes when the repair is not safe.

## Existing Coverage / Deduplication

- u51 owns number bolding and reader-format helpers.
- u61 owns summary candidate validation.
- u71 owns first-viewport reflow.
- u81 owns reader-format package boundaries.
- u100 owns first surface-quality issue codes.
- This unit adds a bounded second issue matrix; it does not introduce a full Markdown parser or spellchecker.

## Scope Boundary

In scope:
- Validate timestamp watermark grammar.
- Repair signed-number emphasis tokenization.
- Block malformed bold/link fragments in public prose.
- Reject public hrefs containing `...` or `…`.
- Detect bounded first-viewport truncation residue.
- Repair or block `민감도을`.
- Keep `불강한성` as a u100 regression fixture only; do not reimplement its repair logic.

Out of scope:
- Full Markdown AST parsing.
- Broad Korean grammar correction.
- Body-wide style editing.
- Watchpoint field normalization owned by u110.
- Historical archive backfill.

## Stage Decision

Functional Design: skip. This is a bounded deterministic validator/repair extension.

NFR Requirements: skip. No new dependency, source, secret, network call, or significant runtime cost.

## Fixed Contracts

### New Issue Codes

| Code | Severity | Region | Behavior |
|------|----------|--------|----------|
| `watermark.window_bracket` | block | first viewport | require balanced `[...]` window after `**기준 시각**:` |
| `markdown.broken_numeric_bold` | block after repair | public prose | repair fixed sign-number-unit tokens; block leftovers |
| `markdown.href_ellipsis` | block | public prose | reject links whose URL contains `...` or `…` |
| `summary.truncated_mid_token` | block | first viewport | reject bounded observed truncation residues only |
| `korean.bad_particle.mingamdo_eul` | warn after repair | public prose | replace `민감도을` with `민감도를`; block if still present |
| `bad_token.bulganghanseong.regression` | block | public prose | assert u100 repair already removed `불강한성`; do not add a second repair path |

### Watermark Contract

Scan only the first line in the first viewport that starts with `**기준 시각**:`.

Valid line grammar:

```text
**기준 시각**: YYYY-MM-DD HH:MM {TZ_LABEL} · 수집창 [{WINDOW_TEXT}]
```

Rules:

- `YYYY-MM-DD HH:MM` must be zero-padded.
- `{TZ_LABEL}` must be one of the existing segment labels emitted by `_render_timestamp_watermark()`.
- Exactly one bracket pair is allowed after `수집창`.
- Nested brackets and extra `[` or `]` are blocking.
- Missing market-window bracket after `수집창` is blocking.
- No other first-viewport line is scanned as a watermark.

### Numeric Emphasis Contract

The emphasis producer may bold these tokens, but must never split them. Valid outcomes are either the exact unbolded token or one bold wrapper around the whole token.

| Input token | Valid bold output |
|-------------|-------------------|
| `-0.04%p` | `**-0.04%p**` |
| `+0.29pp` | `**+0.29pp**` |
| `-$0.23` | `**-$0.23**` |
| `$2.30T` | `**$2.30T**` |
| `+0.74달러(+0.97%)` | `**+0.74달러(+0.97%)**` |

Invalid leftovers include `**-**0.04%**p**`, `**+0.74달러(**+0.97%**)**`, `$2.30**T`, and any nested bold marker inside the token. Reader-format may only prevent new malformed fragments; `_internal.surface_quality` blocks residual fragments after all formatting passes.

### Href Ellipsis Contract

Scan these public Markdown link targets outside protected regions:

- inline links `[text](url)`
- image links `![alt](url)`
- reference definitions `[id]: url`
- autolinks `<https://...>`

Do not scan:

- visible link text when the target is clean
- code spans or fenced code blocks
- raw HTML anchors in collapsed diagnostics
- structured metadata or logs

`[긴 제목...](https://example.com/full)` is allowed. `[긴 제목](https://example.com/...)` is blocked.

### Truncation Contract

Do not implement a general Korean spellchecker. Block only observed residue shapes in first-viewport summary/callout lines:

- line ends with `...` or `…` after a non-space Korean syllable
- line ends with a single-character denylist residue: `채`, `확`, `민`, `관`
- line ends with an unmatched opening parenthesis, bracket, or bold marker

Allow common valid one-syllable endings: `중`, `등`, `후`, `전`, `내`, `외`, `상`, `하`, `및`.

### Protected Regions

Inherit u100 protected-region behavior. Add explicit fixtures for fenced code blocks, inline code spans, markdown tables, collapsed diagnostics, footers/disclaimers, and structured metadata snippets.

## Implementation Steps

- Extend `src/investo/_internal/surface_quality.py` with the new issue matrix.
- Update `src/investo/publisher/reader_format/emphasis.py` so signed number and unit patterns are bolded as one token.
- Add a safe repair pass for `민감도을` and fixed broken numeric-bold patterns.
- Add href scanning that inspects Markdown link targets rather than visible text only.
- Add first-viewport truncation checks using only the bounded denylist/allowlist contract above.
- Enforce the stricter scan in `src/investo/publisher/segment_reader_format.py` before archive/index writes.
- Update summary validation tests so broken candidates cannot be selected as `오늘의 결론`, `핵심 동인`, or `주의할 점`.
- Add a u100 regression assertion that `불강한성` is absent after the existing u100 repair path.

## Acceptance Criteria

1. Segment markdown with malformed `**기준 시각**:` window brackets is blocked.
2. Signed numeric tokens are either correctly bolded as one token or left unbolded; they are never split into malformed fragments.
3. Markdown links with ellipsis in the href are blocked before publish.
4. First-viewport summary lines cannot end with the bounded truncation residue patterns.
5. `민감도을` is repaired to `민감도를` in public prose.
6. Protected regions from u100 remain protected.
7. Summary extraction cannot select a line with a blocking surface issue.
8. `불강한성` remains covered by u100 regression tests and is not reimplemented in u112.

## Minimum Test Matrix

| Issue code | Required tests |
|------------|----------------|
| `watermark.window_bracket` | valid line, missing bracket, extra bracket, nested bracket, non-watermark line ignored |
| `markdown.broken_numeric_bold` | each numeric token valid bold/unbolded, invalid partial wraps blocked, idempotence |
| `markdown.href_ellipsis` | inline/image/reference/autolink target blocked, visible-text ellipsis allowed, code/protected ignored |
| `summary.truncated_mid_token` | denylist residues blocked, valid one-syllable endings allowed, unmatched marker blocked |
| `korean.bad_particle.mingamdo_eul` | repair, warning after repair, block if repair path leaves token |
| `bad_token.bulganghanseong.regression` | u100 repair still removes token before u112 scan |

## Tests / Validation

```bash
uv run --extra dev pytest tests/unit/internal/test_surface_quality.py tests/unit/publisher/test_reader_format.py tests/unit/publisher/test_segment_reader_surface_quality.py tests/unit/briefing/test_summary_quality.py tests/unit/briefing/test_summary_extraction_surface_quality.py
uv run --extra dev ruff check src/investo/_internal src/investo/publisher/reader_format src/investo/publisher/segment_reader_format.py tests/unit/internal tests/unit/publisher tests/unit/briefing
uv run --extra dev mypy src
```

## Non-Goals

- No full Markdown parser.
- No Korean spellchecker.
- No body-wide copy rewrite.
- No watchpoint semantic cleanup.
- No archive backfill.
