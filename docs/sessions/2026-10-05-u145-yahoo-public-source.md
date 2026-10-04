# u145 — public Yahoo source replacement

## Authorization and scope

The user instructed `그럼 그냥 공개용으로 진행해줘` on 2026-10-04 after being told that
Yahoo automated collection/public-use permission had not been verified. The implementation
therefore continues as a public product under a u145 operator exception. This is not provider
consent or a verified license. Free-only remains binding. The original u140 gate and private
u139 NAV product are unchanged. Browser acceptance stays `WAIVED / NOT_EXECUTED`.

Prior scoped branch commit/push and five isolated probes remain authorized. This slice prepares
the replacement and qualification without main integration, public navigation, scheduling,
Telegram or daily-briefing coupling. The branch is `codex/u145-resume-20260922` in the isolated
`.tmp/u145-resume-20260922` worktree; unrelated root changes are preserved.

## Implemented contract

- Replace the paused HF production adapter with Yahoo chart daily JSON at the single fixed
  query2 host/path. No key, credentials, fallback, redirect following or challenge bypass.
- SPY and all eleven sector ETFs, including XLRE. Validate complete responses before retaining
  the calculation window; reject bad rows, dates, identity, currency, granularity and OHLCV.
- Public schema 2, `yahoo-chart-daily-v2`, `price_*` derived fields, provider-reported scope,
  `quote.close` semantics, Yahoo attribution and unverified-permission metadata. No HF/IEX
  license claim or raw public price history.
- Keep same-as-of/freshness gates, partial coverage floor, source-neutral metric kernels,
  canonical pair verification and recoverable store behavior.
- Update the workflow, benchmark, CLI and narrowly scoped provider guard. Historical HF probe
  tooling/reader extra remains available for evidence reproduction, outside the active path.
- Two concurrent sector requests; at most 36 attempts/collection and per minute; 1 MiB/response,
  256-row structural ceiling, 200-calendar-day request window, 120-second collection,
  30-second CPU and 256 MiB incremental RSS. These are application limits, not Yahoo quotas.

## Local validation

The initial focused suite reported 372 pass / 3 failures, all superseded fixture expectations:
request ordering, the old IEX label, and a rank denominator that became valid with XLRE added.
Those assertions were corrected to the new contract; the production rules were not relaxed.

- Full regression: **5,543 passed in 570.88 seconds**. Includes u139 private compatibility,
  models, metrics, rendering/store negative paths, workflow and provider-guard mutation tests.
- Final Yahoo adapter suite after adding exponent-overflow rejection: **79 passed in 16.32 s**.
  Full regression was collected before this last defensive check; this suite covers it directly.
  A subsequent review also identified response decompression before the byte gate; the adapter
  now rejects compressed encodings before body iteration. Final related-suite evidence follows.
- Ruff check/format: pass, 609 files; strict mypy: pass, 270 source files.
- No-paid/provider, no-Anthropic, curated-asset and image-store guards: pass.
- Strict MkDocs build and Material light/dark image-pair contract: pass.
- Local live production probe: **qualified**, 12/12 symbols, 11 available/comparable sectors,
  fresh target/as-of **2026-10-02**, 12 successful requests, no failures/reasons; collection
  1,349 ms, CPU 970 ms, total 2,307 ms.
- Live snapshot id: `sha256:838023f96f0c8deee3d2839849d296f0b5f7a7e8815d998f09bacdd7150cd2ee`.
- Synthetic resource gate: **pass**, 12 responses of 1,048,576 bytes, all 140 trading dates
  in the pinned 200-day window; CPU 1,127 ms, wall 1,262 ms, peak RSS increment 43,843,584 bytes.
- Local review artifact: `.tmp/u145-yahoo-public-preview/site/u145-preview/live/index.html`.
  The live derived pair and five synthetic states passed canonical verification and strict
  HTML structure checks (11 rows, responsive metadata, limitation/source labels before table).
  Local artifact/evidence only; Browser visual execution remains waived, not a visual PASS.

## Independent review and Actions

Independent reviewer `u145_yahoo_review` approved the implementation. The sole P2 finding
(compression decoded before the byte limit) was reproduced, repaired by pre-body encoding
validation, and covered by gzip/deflate/br/combined-encoding tests. No outstanding findings or
new technical debt remain. Review applied security, concurrency, data-integrity, lifecycle,
error-contract, memory and performance protocols.

Final adapter/probe/provider-guard suite: **160 passed in 30.85 s**. Final Ruff check/format and
strict mypy pass. The repaired live production path again qualified 12/12 symbols and 11
comparable sectors with the same target/as-of and snapshot id: collection 1,576 ms, CPU 947 ms,
total 2,449 ms. Resource benchmark again passed: CPU 1,103 ms, wall 1,165 ms, peak RSS increment
45,039,616 bytes.

The reviewed implementation was committed and pushed as
`ec7ac84b927a78e5f3e5f0f3dac6494bb9a7ac6b`. Five sequential, isolated Ubuntu Actions runs
on that exact commit **all succeeded**. Each resource benchmark passed and each production
probe qualified 12/12 symbols, 11 comparable sectors, 12 successful requests, no failed attempt
or terminal reason, fresh target/as-of 2026-10-02 and the same canonical snapshot id.

| Run | Production duration | Collection duration | Resource RSS increment |
| --- | ---: | ---: | ---: |
| [37213980547](https://github.com/murphyGo/investo/actions/runs/37213980547) | 1226 ms | 539 ms | 23556096 B |
| [37214093128](https://github.com/murphyGo/investo/actions/runs/37214093128) | 1302 ms | 628 ms | 23707648 B |
| [37214127663](https://github.com/murphyGo/investo/actions/runs/37214127663) | 1354 ms | 958 ms | 23654400 B |
| [37214182986](https://github.com/murphyGo/investo/actions/runs/37214182986) | 1231 ms | 559 ms | 23904256 B |
| [37214258087](https://github.com/murphyGo/investo/actions/runs/37214258087) | 1297 ms | 627 ms | 24010752 B |

Machine-readable aggregates: [Actions evidence](2026-10-05-u145-yahoo-actions-evidence.json).
The source code, workflow and dependency configuration remain unchanged after those runs;
the final closeout commit contains documentation/evidence only.

Step 5 is complete for the Yahoo source. Step 6 remains separate and unstarted: dedicated
public-write/scheduled workflow, Pages navigation/integration and publication acceptance.
No public sector page or schedule was activated, and no main merge occurred in this slice.
The user-owned dirty root work remains unchanged.
