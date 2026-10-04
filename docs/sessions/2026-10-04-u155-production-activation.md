# u155 Codex production activation — 2026-10-04

## Scope and reviewed configuration

The operator explicitly requested the actual Codex cutover and then confirmed
registration of `INVESTO_PUBLIC_PUBLISH_TOKEN`. Existing Telegram, BEA,
Congress and KRX credentials were reused; no credential values are recorded.

Production execution code is pinned to public commit
`056dd8a1b4a8e599f44519e54b5bf4f486275dbd`. This includes the latest reviewed
news/event code at `95c73a8b` and the existing publication data at `f4d95326`.
The private workflow is copied verbatim from that commit's
`ops/private-runtime/production-briefing.yml`; private installation commit is
`178ab1bc3bb1a09facfde09780cac354c54ee62e`.

The provider is `codex`, model `gpt-6-astra`, native CLI `0.153.4`. The
weekday 07:00 / Saturday 09:00 KST schedule is unchanged. Event briefing and
news window modes remain `shadow`, enrichment remains `off`. Neither repository
had event/news mode overrides. The separate public event-preview workflow is
outside this daily-owner migration and was preserved.

Validation: 49 scoped workflow/runtime tests, 128 independent Codex/event/news
boundary tests, Ruff lint/format, actionlint 1.7.12 and whitespace checks passed.
The reviewer confirmed the pre-publication auth checkpoint and child credential
isolation remain intact. The missing shadow-mode parity was repaired and tested
against the actual public daily workflow.

## Publisher and schedule ownership

- Publisher Secret metadata confirmed registration at 2026-10-04 14:14:04 UTC.
- Private preflight [37209080763](https://github.com/murphyGo/investo-runtime/actions/runs/37209080763)
  passed using only the publisher PAT: destination-scoped Git handshake plus
  real public Pages dispatch. Git dry-run does not prove a real ref update.
- Its Pages run [37209101940](https://github.com/murphyGo/investo/actions/runs/37209101940)
  succeeded at public `f4d9532607fcf742f6a60cec409dfc85e78cef76`.
- Final public Claude run [37208127537](https://github.com/murphyGo/investo/actions/runs/37208127537)
  completed successfully: target 2026-10-02, three usable finalized segments,
  pushed `f4d95326`, Telegram message 147. It was allowed to finish.
- Public `daily-briefing.yml` is `disabled_manually`; in-progress and queued
  run counts were both zero before enabling the private owner.
- Private `CODEX_PRODUCTION_ENABLED=1` and `REVIEWED_CODE_SHA=056dd8a1...`
  were verified from the API. Only the private repository owns the daily
  schedule. Cross-repository concurrency is not relied upon.
- First actual Codex acceptance run:
  [37209545723](https://github.com/murphyGo/investo-runtime/actions/runs/37209545723).
  It intentionally replays 2026-10-02; one additional briefing notification is
  expected. The existing notifier has no duplicate-date suppression ledger.

## First production acceptance — passed

Run `37209545723` completed successfully on 2026-10-04 at 14:35:47 UTC
(23:35:47 KST), after a 4m42s job:

| Boundary | Observed result |
|---|---|
| Provider/model | Receipt confirms `codex` / `gpt-6-astra` at pinned `056dd8a1...` |
| Generation | `ok=3 failed=0` for domestic equity, US equity and crypto |
| Finalization | All three `finalized`, each `codes=none` |
| Auth | `unchanged`, supervisor exit 0; prior refresh/persist/reuse evidence remains valid |
| Publication | Actual Contents write succeeded; public commit `e5e59729e329c7199e7406e91015b36188155b74`, parent `056dd8a1...` |
| Telegram | Briefing message 148 sent successfully after push |
| Runtime | Pipeline 245.888s, supervisor 246.295s |
| Pages | [37209833667](https://github.com/murphyGo/investo/actions/runs/37209833667) succeeded on exact publication SHA |
| Shadow parity | Event-shadow logs for all three markets; news-window logs keep `fetch_changed=false cursor_write=false` |

Pages push run `37209830260` and the explicit fallback dispatch raced while the
new push run was becoming visible. Pages concurrency cancelled the push run;
the dispatch above completed successfully at the same SHA. This did not repeat
the briefing or Telegram call.

Full quality [37209456374](https://github.com/murphyGo/investo/actions/runs/37209456374)
at execution SHA `056dd8a1...` passed: **6,149 tests**, Ruff, mypy (290 sources),
policy/assets guards, strict docs and Material theme contract. The operational
switch and acceptance are complete. Account billing visibility below remains
an explicit unverified N155-15 item; it is not marked as passed.

## Usage visibility and token lifecycle

The operator reports no prior Actions billing charges and requested the actual
cutover. It is not evidence of unlimited private Actions. The latest successful
full dry-run took 375.588 seconds (job approximately 6m46s). At that measured
job duration, October's 27 scheduled runs estimate about 183 runner minutes,
before retries, qualification jobs, slower runs or other repositories. The first
production job measured 4m42s; the 183-minute estimate retains the slower
qualification sample and is not a hard monthly cap.

Account-wide October allowance and spending-limit verification remains open:
the current billing API returns 404 and requires a missing `user` scope. The
September report of 2,000 included remaining minutes is historical. No account
scope expansion, billing-plan change, spending-limit change or paid API fallback
was performed. Activation proceeded under the operator's repeated actual-cutover
request using the existing account configuration; this does not close the
unverified billing portion of N155-15.

`CODEX_SECRET_WRITE_TOKEN` already proved actual encrypted auth write-back and
next-job reuse. GitHub PAT expiration is not automatically renewed. Both the
writer PAT and publisher PAT must be replaced by the operator before their
selected expiration dates; those dates are not exposed by Secret metadata.
Managed ChatGPT auth refresh is persisted automatically when it changes.

## Rollback

Set private `CODEX_PRODUCTION_ENABLED=0`, disable its daily workflow, and wait
for every active/pending private daily job to finish. Inspect the latest public
commit and Telegram message before replaying a date. Only then re-enable the
public daily workflow. Never run both daily owners or share the managed Codex
auth stream with another runner. There is no automatic Claude/API fallback.
