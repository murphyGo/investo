# u149 Numeric Claim Local Containment and Minimal Fallback

## Status

Complete through production Step 7b on 2026-09-02. The two exact-date replays published all three segments, delivered Telegram, completed their chained Pages deployments, and passed live domestic archive checks.

## Delivered boundary

- Domestic numeric-only findings reach indexed ownership and use deterministic whole-claim, row, H3, or owned-region containment.
- Recovery is eligible only when the exhaustive original hard-code set is exactly `numeric.anchor_assertion`; simultaneous compliance/entity/structure/disclaimer defects remain blocked.
- Residual or protected numeric-only content receives one no-LLM neutral six-section minimal source through the same u144 finalizer and seal.
- Sealed containment witnesses produce `finalized_degraded`, which counts as a published document for completeness/exit/Pages/Telegram behavior.
- Logs and quality history project bounded witness metadata and never emit the original claim.

## Validation

- Final source/containment review regression: 37 passed; the earlier cumulative U148/U149/U144 scope passed 314 tests.
- Explicit regressions cover local table-row exclusion, protected-region minimal fallback, numeric+compliance masking prevention, US-policy preservation, and one builder call across survivor reruns.
- Full repository suite: 4,334 passed in 448.30 seconds.
- Ruff check passed; Ruff format passed for 559 files; strict mypy passed for 254 source files; lock, no-paid API policy, strict MkDocs, and diff-integrity checks passed.
- Fresh-eyes review closed all parser, indexed-edit, stale-offset, artifact-promotion, complexity, and newline-boundary findings; final verdict had no remaining Critical, High, Medium, or Low issue.
- Production Step 7b:
  - 2026-08-03: daily run `33543213131` succeeded with pipeline rc 0; domestic `finalized_degraded` used two `rewritten` actions (`^KOSPI` and `^KOSDAQ`, both `section:3`), while US and crypto were `finalized`. Telegram returned HTTP 200. Bot commit `fafc7d1561d96764b8c5407724a71064c2568959` published all three documents and chained Pages run `33544427195` succeeded.
  - 2026-08-04: daily run `33547421276` succeeded with pipeline rc 0; domestic `finalized_degraded` used four `rewritten` actions (`^KOSPI` in `section:2` and `section:3`, `^KOSDAQ` in `section:3`, and `005930.KS` in `section:5`), while US and crypto were `finalized`. Telegram returned HTTP 200. Bot commit `a05cd3131fa709ec1e010517304e394dbcee4210` published all three documents and chained Pages run `33548610376` succeeded.
  - Live domestic URLs returned HTTP 200: `https://murphygo.github.io/investo/archive/domestic-equity/2026/08/2026-08-03/` and `https://murphygo.github.io/investo/archive/domestic-equity/2026/08/2026-08-04/`. Neither the committed Markdown nor live HTML contained the incident values `150.00`, `344.00`, `483.00`, `7,500.00`, or `7500.00`; the unsafe exact claims were replaced with bounded data-limited wording.
  - Source health remained distinct from content degradation. Both runs reported `market_anchor domestic=0`; 2026-08-03 returned zero rows from `fsc-krx-index-price` and `yonhap-index-close`, while 2026-08-04 recorded transient FSC index/stock failures and zero Yonhap index rows. Those source outcomes remained observable even though the domestic document sealed as `finalized_degraded` and the bundle exited 0.
  - Operational observation: the pipeline steps took 11m46s and 11m33s, so both exceeded the project NFR-001 ten-minute target. This does not invalidate AC-149.17's correctness/delivery closeout; it is tracked separately as DEBT-090.
