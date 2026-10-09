# u145 Step 5 — implementation validation and external qualification gate

## Current outcome

The approved implementation and two live-found repairs are pushed on
`codex/u145-resume-20260922`. The final application/workflow commit is
`90f09d990ddfa4c97624a6dc63a722785b76c379`. Step 5's Ubuntu resource gate passes, but live
qualification is **0/5** because the provider's download-token endpoint is unavailable.
Step 5 is not complete. Step 4's user waiver remains `WAIVED / NOT_EXECUTED` and Step 6
public activation remains separate and unstarted.

## Executed Actions evidence

| Run | Commit | Resource gate | Live result | Counts toward 5 |
| --- | --- | --- | --- | --- |
| [36262389388](https://github.com/murphyGo/investo/actions/runs/36262389388) | `ab1c06c3` | Failed: 288,579,584-byte RSS increase | Skipped | No |
| [36262917373](https://github.com/murphyGo/investo/actions/runs/36262917373) | `fe046fb4` | Passed: 133,963,776 bytes | Token envelope mismatch, one accepted response | No |
| [36333562285](https://github.com/murphyGo/investo/actions/runs/36333562285) | `90f09d99` | Passed: 135,847,936 bytes | 11/11 symbols, 22/22 requests; stale 2026-09-24 vs target 2026-09-25 | No |
| [37127718087](https://github.com/murphyGo/investo/actions/runs/37127718087) | `90f09d99` | Passed: 134,094,848 bytes | Three retryable token-status failures, zero accepted responses | No |
| [37127886681](https://github.com/murphyGo/investo/actions/runs/37127886681) | `90f09d99` | Passed: 133,861,376 bytes | Same three-attempt server failure | No |

Closed aggregate evidence is recorded in `2026-10-03-u145-step5-actions-evidence.json`.
Five total executions across different repair commits are not five successful qualification
runs. The next qualification batch must obtain five successful runs on one reviewed commit.

## Repairs and validation

1. Collector retention now discards unneeded history after validating every original row.
   SPY retains 64 observations; sectors retain their SPY-date intersection plus their final
   two IEX observations. All metric, snapshot and rendered-pair outputs match untrimmed input
   across complete, warming, stale, newer-sector, extra-date, missing-date and zero/one-overlap
   cases. Invalid old rows still fail before pruning. Ubuntu RSS is now approximately
   128–130 MiB under the unchanged 256 MiB limit with all 11 x 10,000 synthetic rows.
2. The token validator accepts the five fields in the [official API reference](https://hfdatalibrary.com/pages/api).
   Echoed version/timeframe/format must exactly match clean/daily/parquet. Unknown fields,
   wrong values/types and all original host, credential, byte and string limits still fail.

Both changes received independent review approval. The latest focused adapter/metrics/probe
suite passed **158 tests**. Ruff/format passed for 609 files; strict mypy passed for 270 source
files plus the CLI. Policy/site checks and synthetic benchmarks passed; the resource ceiling
also passed on the actual Ubuntu reference runner as shown above.

Final exact-implementation full-suite result: **5,563 passed in 615.76 seconds**, exit 0,
zero failures/errors/skips. Its durable result is
`.tmp/step5-evidence/pytest-final-20261003.xml`. All application/workflow files remained
identical to `90f09d99` throughout the final run. The five recorded runs also passed
closed-evidence model validation with zero qualifying successes.

## Provider state and next executable action

At 2026-10-03T13:54Z, the unauthenticated public status endpoint returned operational and
public SPY metadata returned HTTP 200. The [public catalog](https://hfdatalibrary.com/data/metadata.json)
advertised data through **2026-10-02**, updated at `2026-10-03T12:53:42Z`. These are public
catalog/service observations; they do not prove that each credentialed daily file is fresh.
The [provider status page](https://hfdatalibrary.com/pages/status) also distinguishes service
availability from data freshness and describes next-morning publication.

The unauthenticated daily/Parquet/clean token request returned **HTTP 503**, reproduced again
at 23:07 and 23:31 KST. In both authenticated Actions probes the adapter made the allowed three attempts
and returned `source.status` with zero successful responses. Thus the current blocker is the
download-token path. No authentication-rejected result was observed; no key value was read,
printed or changed. Secret-name metadata still showed the 2026-09-01 update timestamp.

After the provider endpoint recovers, rerun the registered manual workflow sequentially on
one reviewed branch commit and count only fresh complete qualified results. Apply the existing
key-rotation procedure only if authentication is then rejected. Do not waive freshness or
change source, URL, date or resource limits to manufacture green runs.

No raw provider data, signed URL, public sector pair, Pages/navigation/schedule change,
Telegram message, daily-briefing integration or main-branch merge was produced. The root
worktree's unrelated dirty files remain untouched. This documentation-only closeout is
covered by the existing commit/push approval and preserves the tested application/workflow tree.
