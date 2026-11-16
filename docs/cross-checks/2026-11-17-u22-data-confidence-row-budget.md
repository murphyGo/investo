# u22 row-budget follow-up cross-check — 2026-11-17

Status: **PASS for the bounded local repair**. This does not certify a production release or unrelated units.

| Requirement / acceptance criterion | Implementation and evidence | Result |
|---|---|---|
| FR-002/003, u22 source truth | Builder projects existing `SegmentCoverage`; test asserts unchanged outcomes, status, counts, missing categories, and reasons | Pass |
| FR-017 diagnostic transparency | Failed → zero → skipped → ok; exact adapter counts and explicitly representative details; healthy summary retained | Pass |
| FR-018 deterministic visual assets | Four-row shared budget; incident combination completes asset creation, light/dark, provenance, relative links | Pass |
| NFR-003 reliability, narrow incident AC | Observed 13-row error removed; both logged-outcome replay variants now return four rows; 5/12/13/1,000-source tests | Pass |
| NFR-004 disclaimer | Existing card and briefing disclaimers asserted through actual asset preparation | Pass |
| NFR-005 maintainability | Same-module shared constant, small pure helpers; no boundary/dependency changes | Pass |
| NFR-006 testing / R13 redaction | 590 related tests passed; sanitized error and XML escaping regression; synthetic outcomes clearly labeled | Pass |
| Backward compatibility | At most four rows unchanged; twelve-row direct-input schema and defensive renderer truncation preserved | Pass |
| Public wording | Source-count nouns survive the unchanged reader-language projection; forbidden-fragment assertion passes | Pass |

Independent reviewer found no issues and checked 1,296 status-count combinations. Ruff, format, Mypy, and diff checks pass. Local light/dark preview inspection used an explicit installed Korean font substitution because Cairo's default font fallback lacked Korean glyphs; production SVG code is unmodified in that respect.

Evidence and exact commands: `aidlc-docs/construction/u22-source-coverage-transparency/code/row-budget-summary-20261117.md`; review and sanitized replay JSON are adjacent. Private job logs are excluded. No production LLM, publishing, messaging, or deployment was run. Production article completion and unrelated domestic classification failures remain unverified by this change.
