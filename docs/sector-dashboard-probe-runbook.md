# u145 production-adapter probe runbook

## Scope and decision

The manual `sector-dashboard-probe.yml` workflow qualifies the production Yahoo daily-chart
collector, public price metrics and canonical renderer. It publishes no sector page.
The user authorized public Yahoo implementation on 2026-10-04 after the permission uncertainty
was explained. This operator exception is not provider consent or a verified data license.
See the [active design amendment](../aidlc-docs/construction/u145-sector-dashboard-public-hf-limited-radar/source-qualification/2026-10-04-yahoo-public-amendment.md).

HF is superseded following its explicit `data_paused` response. The earlier
`scripts/probe_hf_data_source.py` and HF evidence remain historical and do not qualify Yahoo.
The `sector` dependency extra is retained for that historical Parquet tooling; the current
collector and workflow need only core dependencies. No API key is required or forwarded.

Step 4 visual acceptance remains user-waived (2026-09-27), `WAIVED / NOT_EXECUTED`.
This does not waive data validation, resource limits or the operational checks below.

## Execution

Use a reviewed commit pushed to the isolated branch. Dispatch sequentially and wait for
completion before dispatching another run; five dispatch requests are not five executions.

```sh
gh workflow run sector-dashboard-probe.yml --ref codex/u145-resume-20260922
gh run list --workflow sector-dashboard-probe.yml --branch codex/u145-resume-20260922 --limit 5
gh run view RUN_ID --log
```

The workflow is manual, `contents: read`, checkout credentials disabled, no cache, raw artifact,
Pages or Telegram step. It installs locked core dependencies, runs the synthetic resource gate,
and invokes:

```sh
uv run --frozen --no-sync python scripts/build_sector_dashboard_public.py --probe-only
```

There is no write mode, date override, URL/symbol override or fallback. The only endpoint is
HTTPS `query2.finance.yahoo.com/v8/finance/chart/{ticker}`. Requests ask for daily bars between
midnight New York target-minus-200-days and midnight after the target date. Current intraday
bars cannot enter the completed-session calculation. The target uses the versioned 2026 NYSE
calendar: regular close 16:00 New York, 13:00 on November 27 and December 24, as pinned from the
[NYSE calendar](https://www.nyse.com/trade/hours-calendars) on 2026-09-27. Unknown years fail
before the probe requests data.

Only `quote.close` feeds simple price-return metrics, never `adjclose`, NAV, volume or fund
flow. Source metadata is schema 2, `yahoo-chart-daily-v2`, with public-use permission unverified.

## Qualifying evidence

Require five distinct successful runs on the exact reviewed implementation commit. Each needs:

- passing `synthetic_resource_benchmark`;
- `production_adapter_probe` status `qualified`;
- all 12 symbols (SPY and 11 sector ETFs, including XLRE), 11 comparable sectors;
- fresh data, equal target/as-of dates, canonical snapshot identity and no terminal reasons;
- bounded request count and resource measurements, plus run and commit ids.

Eight through ten comparable sectors can satisfy the product's partial-publication floor,
but cannot qualify this gate. XLRE now follows the same rules as every other sector. HTTP 200
within the media/byte envelope counts as a successful response; a subsequent schema failure
still fails that symbol and the probe. Retries may recover a transient response.

Resource ceilings: 1 MiB JSON and 256 rows per response, two concurrent sector requests,
36 requests/minute and 36 attempts/collection, 120-second collection, 30-second CPU and
256 MiB incremental peak RSS. These request limits are application policy, not a Yahoo quota.
Compressed responses are rejected before body decoding; 401/403 are terminal; 429, server and transport errors have at most two bounded retries.

The synthetic benchmark sends twelve 1 MiB responses containing every valid trading date in
the 200-day window (140 observations at the pinned fixture date). Whitespace fills the response
to the byte ceiling; separate tests reject excessive rows, dates, nesting and invalid values.
It includes cold imports and fixture generation. Each GitHub Ubuntu run must pass the resource
gate independently of local macOS evidence.

Only closed aggregate evidence reaches stdout and Step Summary. Raw rows, response bodies or
headers, rendered pairs and configured secrets are excluded. A synthetic run, historical HF
success or local Yahoo success does not substitute for five fresh Actions executions.

## Failure handling

The probe exits 0 only for qualified data; other results exit 2. Preserve the limits and
investigate the closed reason instead of weakening qualification.

| Closed code | Operator action |
| --- | --- |
| `auth.configuration` | Remove injected client hooks, cookies or default query parameters; check budget consistency. No API key is expected. |
| `auth.rejected` | Yahoo rejected unauthenticated access. Stop and requalify the source; do not add credentials, proxies or challenge bypasses. |
| `source.throttle` / `source.transport` | Wait for recovery and rerun within the same ceilings. |
| `source.status` | Check endpoint availability; repeated 5xx may need provider recovery. |
| `source.schema` / `source.row` / `source.response_size` | Requalify changed response shape before modifying the strict parser. |
| `source.calendar` / `source.freshness` | Check completed session, source dates and supported calendar year. |
| `probe.coverage` | Wait for the complete universe and enough history. |
| `probe.resource` | Reproduce with synthetic data and retain production ceilings. |
| `probe.projection` / `probe.output` / `probe.internal` | Investigate with synthetic inputs; never log raw provider exceptions. |

Cancel a specific run or disable the manual workflow to stop qualification. Failed probes
leave public pages unchanged. Five successes allow preparation/review of Step 6; they do not
enable scheduling, public writes, navigation or deployment automatically.
