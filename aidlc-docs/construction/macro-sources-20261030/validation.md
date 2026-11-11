# Validation — macro sources 2026-10-30

Implementation base: public `91cbbb019e7f9538ac1e6371605325cce4018955`. Isolated checkout: `/private/tmp/investo-macro-sources-20261030`. Shared working tree integrated by three-way content merge; index and unrelated changes preserved.

- Independent review: PASS, 117 independently executed tests, no remaining C/H/M. See review.md.
- Isolated focused + existing publication/plugin/channel/reader suite: 124 passed.
- Integrated root with earlier data-expansion regression suites: 211 passed in 2.88s.
- Ruff check/format: PASS; root 867 files. Mypy: PASS, 369 source files.
- Node22 behavior suite: 39 passed. No-paid and no-Anthropic-SDK guards: PASS.
- Curated asset/image-store checks, strict MkDocs build and Material/calendar contracts: PASS.
- Live adapter execution: three successful no-key source fetches, one valid reference item each; latency 0.459–1.187s. See live-check.json. No sends or publications.
- Full isolated Python3.11.9 pytest: 7,847 passed, 3 failed, 1 known skip in791.05s. Two failures were missing Node PATH; one was the existing fixed registry-count assertion (47 before additions, now50). With Node22 PATH and count updated, all three failing cases plus their relevant suites passed:15/15 in13.53s. Combined evidence validates7,850 cases plus1 known skip; this is full execution followed by focused correction verification, not a second all-green full run.

New tests cover recorded byte/hash replay, source identity, four-row TGA reconciliation and null trap, latest GSCPI vintage/month/padding, OFR aggregate/date/finite values, malformed/duplicate/oversized payloads, stale/future observations, UTC normalization/NY cutoff, retry limits, sibling failure isolation, mandatory actual health, news reservation, forged legacy/native values, missing-source removal and adjacent owned content preservation.

Local construction only: no commit, push, production/preview pin update, workflow dispatch, public archive rewrite or Telegram send. First runtime/GHA reachability and scheduled output acceptance are release-stage follow-ups.

Final source-code changes after independent review were documentation-only; the registry regression fix changes a test assertion from47 to50. Final Ruff and diff whitespace checks pass.


## 2026-11-11 deployment qualification correction

The current official CSV was fetched before production promotion: decoded338194bytes, sha256`ef5109319ee888d704a5512ec4790b929c38d07069085138765f1229125f4328`. It uses Excel1900 month serial headers, `#N/A` missing cells and up to18 fractional digits, unlike the October30 fixture. The adapter now accepts the observed serial representation (ASCII5digits, epoch1899-12-30, month-first, years2000–2099) alongside named-month vintages; equivalent duplicate vintages still fail. Sparse vintage months are valid.

GSCPI values remain finite plain decimals with absolute magnitude≤100, maximum18 fractional digits and3 integer digits. Bounds and conflicting duplicates are checked before rounding; display uses six decimal places with half-even rounding under an explicit32-digit Decimal context. Both publication paths disclose this formatting. Unknown missing/error strings, scientific notation, malformed/future vintages and conflicts remain closed failures or empty future-cutoff results as specified. Existing network/row/byte/time caps are unchanged. New byte-exact fixture retains NYFed attribution/terms and is paired with precision, stale-cutoff, duplicate and malformed-input tests.

Local correction verification:142 tests pass on public and runtime candidates; Ruff/format and mypy pass. Exact final-SHA CI and production pin readback will be recorded in the release receipt.
