# u145 production-adapter probe runbook

## Scope

The manual `sector-dashboard-probe.yml` workflow qualifies the production HF adapter, public
metrics and canonical renderer. It does not publish a sector page. The earlier Step 0 script,
`scripts/probe_hf_data_source.py`, remains source-qualification history and is no longer the
workflow entrypoint. Its previous successful runs do not count toward Step 5.

The Step 4 visual gate is user-waived as of 2026-09-27; actual viewport execution remains
`NOT_EXECUTED`. This exception does not waive any data, security or operational check below.

## Prerequisites and execution

- Use a reviewed commit containing the Step 1–5 code and the locked `sector` dependency extra.
- Keep the operator-owned HF account verified and its 30-day key in the repository Actions
  secret `HF_DATA_API_KEY`. Never pass the key as a workflow input or CLI argument.
- The workflow is manual only, with `contents: read`, checkout credential persistence off,
  and no Actions cache, raw data artifact, Pages or Telegram step.
- The secret is exposed only to the live probe step, after dependency installation and the
  synthetic resource gate have finished.

After the reviewed commit has been pushed to the isolated branch, dispatch sequentially:

```sh
gh workflow run sector-dashboard-probe.yml --ref codex/u145-resume-20260922
gh run list --workflow sector-dashboard-probe.yml --branch codex/u145-resume-20260922 --limit 5
gh run view RUN_ID --log
```

Replace `RUN_ID` with the returned integer. Wait for each run to finish before dispatching the
next. Concurrency prevents overlap, but rapid repeated dispatches can replace queued runs;
five accepted dispatch requests are not evidence of five completed executions.

The live command is:

```sh
uv run --frozen --no-sync python scripts/build_sector_dashboard_public.py --probe-only
```

There is no write mode, date override, URL/symbol override or fallback source. Date resolution
uses the versioned 2026 NYSE calendar and the latest completed regular session: 16:00 New York
time normally, 13:00 on November 27 and December 24. Those early closes are pinned from the
[NYSE official calendar](https://www.nyse.com/trade/hours-calendars), verified 2026-09-27.
Unknown calendar years fail before network access. Measured collection duration above 120
seconds or CPU above 30 seconds blocks qualification, including synchronous-decoder overruns
that an asynchronous timeout cannot interrupt.

## Qualifying evidence

Count only five distinct successful workflow runs on the exact reviewed commit, each with:

- a passing `synthetic_resource_benchmark` result;
- `production_adapter_probe` status `qualified`;
- 11 successful supported symbols (SPY plus ten sectors), 10 available/comparable sectors,
  fresh data and equal target/as-of dates;
- a verified canonical snapshot identity and zero terminal reason codes;
- bounded request counts, collection duration, total duration and the workflow run/commit ids.

The permanent XLRE absence is expected and is not a failed request. A snapshot with eight or
nine supported sectors may satisfy the product's partial-publication floor, but it does not
qualify a five-run rollout gate. Retries can recover transient requests; accepted HTTP responses
and unsuccessful attempts are counted separately from final per-symbol collection outcomes.
Successful responses mean HTTP 200 bodies read within the media/size envelope, not necessarily
schema-valid bars. A later schema error remains a failed symbol and a blocked probe.

The synthetic benchmark uses eleven 10,000-row in-memory Parquet series through the same
adapter/metrics/renderer. It verifies `pyarrow==25.0.1`, the 2 MiB response ceiling, 22 clean
requests, CPU <=30 seconds, wall time <=120 seconds, and peak RSS increase <=256 MiB above its
interpreter baseline. It includes cold imports and fixture generation conservatively. Local
macOS measurements are preliminary; each GitHub Ubuntu run must pass the reference gate.

Only closed aggregate evidence reaches stdout and GitHub Step Summary. No raw rows, signed
download URLs, provider bodies/headers, rendered pair or API key is retained in an artifact.
Record the five run ids, head commit, target/as-of, counts, timings and closed outcomes in the
Step 5 session evidence. A synthetic result or historical Step 0 run cannot substitute for
a fresh production-adapter probe.

## Failure handling and key rotation

The probe exits 0 only when qualified; other outcomes exit 2. Do not weaken a gate to obtain
five green runs.

| Closed code | Operator action |
| --- | --- |
| `auth.configuration` | Confirm `HF_DATA_API_KEY` exists and is a valid non-placeholder key. |
| `auth.rejected` | Replace the expired/revoked key through the operator's HF account and GitHub repository Actions secrets; the key may have reached its 30-day lifetime. |
| `source.throttle` / `source.transport` | Inspect the bounded aggregate result, wait for provider recovery, then rerun; do not increase the limits. |
| `source.schema` / `source.row` / `source.response_size` | Treat as contract drift; return to source qualification before changing the adapter. |
| `source.calendar` / `source.freshness` | Check expected completed session, source availability and the supported calendar year. |
| `probe.coverage` | Wait for the complete supported universe/history; do not count a partial run. |
| `probe.resource` | Inspect aggregate timing/CPU evidence; reproduce with synthetic inputs and retain production ceilings. |
| `probe.projection` / `probe.output` / `probe.internal` | Investigate with synthetic local inputs; do not log raw provider errors to diagnose it. |

For rotation, create the replacement key in the operator-owned HF account, update only
`HF_DATA_API_KEY` in GitHub repository Settings → Secrets and variables → Actions, and rerun
the manual probe. Revoke the old key in HF after the new key succeeds; immediately revoke any
exposed key. Do not put either value in an issue, chat, command argument, commit or session log.
No automatic account registration, verification or rotation is provided.

To stop qualification, cancel the specific run or disable the manual workflow in Actions.
Because this step publishes nothing, a failed probe leaves existing public pages unchanged.
Five successes permit preparation/review of the separate Step 6 activation change; they do
not themselves enable schedule, public writes, navigation or deployment.
