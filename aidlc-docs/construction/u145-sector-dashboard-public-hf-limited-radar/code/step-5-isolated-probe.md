# u145 Step 5 — Isolated production-adapter probe

## Implementation

The existing manual Step 0 workflow now runs a synthetic resource gate and the actual Step 5
production path. `scripts/build_sector_dashboard_public.py --probe-only` owns a bounded,
redirect-disabled, environment-proxy-disabled HTTP client. The public probe composition runs
the existing HF adapter, close-only bundle, snapshot calculation, and canonical renderer/verifier.
It exposes no store/publisher call or write mode. Raw data and the rendered pair remain in memory.

`PublicProbeEvidence` contains a closed aggregate schema. A qualified result requires all eleven
supported symbols, ten comparable sectors, a fresh completed session, a verified snapshot id,
and no terminal failure code. Eight/nine-sector product partials remain valid product inputs,
but fail the five-run rollout qualification. Counters distinguish bounded HTTP response success
from final symbol success; projection failures preserve already completed collection counts.

The CLI accepts only `--probe-only` and reads the key from the existing environment boundary.
There is no historical target-date, URL, symbol, format or key override. Its clock resolves the
latest completed session from the existing 2026 holiday calendar plus NYSE's official 13:00 ET
closes on 2026-11-27 and 2026-12-24. Unknown calendar years fail before network access.
Source: [NYSE calendar](https://www.nyse.com/trade/hours-calendars), verified 2026-09-27.

## Security and operations

- Manual trigger only; `contents: read`; checkout credential persistence disabled.
- Pinned/locked sector-only dependency installation; no Actions cache or data artifact.
- `HF_DATA_API_KEY` is injected only into the live probe step after installation and benchmark.
- No schedule, Pages navigation/deployment, Telegram, public pair write or daily-briefing call.
- One <=4 KiB canonical aggregate JSON goes to stdout and GitHub Step Summary.
- Configured secret values are checked before and after JSON decoding. Generic credential
  screening exempts only typed `snapshot_id`, commit SHA and run-id fields with exact validated
  shapes; every other field remains scanned. Provider/exception text is never interpolated.

Runbook: `docs/sector-dashboard-probe-runbook.md`.

## TS-8 resource gate

`scripts/benchmark_sector_dashboard_public.py` creates eleven synthetic 10,000-row daily
Parquet series in memory and feeds the complete production path through `httpx.MockTransport`.
It checks the pinned wheel, accepted response envelope, 22 clean requests, <=120 seconds wall,
<=30 seconds CPU and <=256 MiB peak RSS above interpreter baseline. Cold imports and fixture
generation are included conservatively. No network call or raw fixture file is made.

The live probe independently rejects measured collection >120 seconds or CPU >30 seconds.
This closes the case where synchronous decoding crosses an async timeout after the last ticker
has already returned. The evidence model also rejects a forged qualified result above either
ceiling. GitHub's Ubuntu reference gate remains required even after a local benchmark passes.

## Review repairs

Independent review reproduced and closed early-close freshness and synchronous deadline-overrun
defects. Projection-failure accounting was corrected to retain actual collection counts.
Real CLI integration tests additionally reproduced false credential matches on legitimate hash
and GitHub metadata fields. The narrow identity exception, canonical exact-secret precheck,
and escaped-secret regression were approved on re-review. The u139 reverse-integration guard
was amended only for the two exact public commands in the dedicated probe workflow; private
runner and all other integration bans remain in place.

Final focused public-probe tests: 46 passed. All added source/CLI code passes strict mypy and
Ruff. Full-suite, policy and site-build outcomes are recorded in the session log:
`docs/sessions/2026-09-27-u145-step5-isolated-probe.md`.

## Gate status

The workflow/CLI implementation and local gates are complete: 5,547 full-suite tests passed
in 581.26 seconds, with unchanged code/configuration hashes throughout the final run.
The five live Step 5 executions and Ubuntu reference benchmark have not yet occurred and
are not replaced by Step 0 history, mock-transport tests, or the local resource benchmark.
Step 6 remains separate and inactive. The earlier screen-validation waiver remains in force;
it is `WAIVED / NOT_EXECUTED`, never a screenshot-based PASS.
