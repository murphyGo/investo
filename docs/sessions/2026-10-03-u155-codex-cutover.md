# u155 Codex operational cutover — 2026-10-03

Historical preparation record. Actual production was activated and verified on
2026-10-04; see `2026-10-04-u155-production-activation.md` for current status.
The account-wide billing visibility item remains open.

## Authorization and scope

The user requested “Codex로 전환하고 싶어. 남은 작업 ㅈ진행해” and
“gogo” after reviewing the incomplete operational status. This authorizes
continuing Steps 8 and 9, including the necessary reviewed fixes, runtime
qualification and production cutover. Existing validation, credential
isolation and no-additional-paid-API requirements remain in force.

Work uses `codex/u155-cutover-20261003` from public `origin/main`
`d240b30376cd4d9c896a98be1482d7c139368ee1`. Unrelated root modifications and
the earlier provisioning worktree are preserved.

## Refreshed starting evidence

- Codex implementation is merged in public main; public daily still uses Claude.
- Public run `37096514850` completed successfully on 2026-10-03.
- Private repository `murphyGo/investo-runtime` and Environment `codex-runtime`
  exist. Both `CODEX_AUTH_JSON` and `CODEX_SECRET_WRITE_TOKEN` names are present.
- Previous real qualification `34388756894` selected `gpt-6-astra` and failed
  all three classification stages with `codex_execution_failed`.
- Private commit `a9e563f8ec99b9490ad6d378e4e280ca01b27da0` was prepared in the
  earlier session but was not pushed. It adds a single-call diagnostic using
  the existing supervisor, bounded capture and auth preservation.
- Fresh independent review found no blocking issue. Five diagnostic tests,
  Ruff and format checks passed. The diagnostic only reports fixed categories;
  raw events, native stderr, model response and credential values are not logged.
- The exact private commit was pushed and verified remotely. Diagnostic
  `37128670838` is the first resumed qualification run.

## Repairs and live qualification

- Diagnostic [37129952151](https://github.com/murphyGo/investo-runtime/actions/runs/37129952151)
  proved the native call succeeded but emitted the pinned CLI's unstable-feature
  startup warning as an error item. Commit `07065426` suppresses that startup
  notice through configuration; tool, reroute, dropped-event and fatal-event
  rejection remain enforced. Diagnostic
  [37130119826](https://github.com/murphyGo/investo-runtime/actions/runs/37130119826)
  then passed with no unexpected events.
- The first full retry generated/finalized all three markets, then exposed a
  dry-run history mismatch: the quality gate compared current output with the
  old canonical ledger. Commit `cf519b8c` builds a temporary history with the
  current snapshot for both dashboard and gate. Real contradictions still fail;
  the canonical history stays unchanged and temporary data is removed on
  success, failure and cancellation.
- Full dry-run [37130989203](https://github.com/murphyGo/investo-runtime/actions/runs/37130989203)
  used `cf519b8c160db7a81ef305188c7cc4141ef29c51`, target `2026-10-02`,
  provider `codex`, model `gpt-6-astra`: generation **3/3**, finalization **3/3**
  (`finalized`, no residual codes), pipeline `success`, supervisor exit **0**,
  **283.882 seconds**, auth `unchanged`. Git commit/push was explicitly skipped;
  Telegram returned `message_id=None`. Public main remained `d240b303` and its
  Claude workflow remained active after the run.
- Diagnostic [37128670838](https://github.com/murphyGo/investo-runtime/actions/runs/37128670838)
  observed real auth rotation and encrypted write-back (`GET` public key 200,
  `PUT` auth Secret 204, receipt `auth=persisted`). Later serialized diagnostic
  and full runs reused that stored Secret, including the successful runs above.
  No raw credential values or CLI events were retained in these records.

## Production preparation and validation

The inactive `ops/private-runtime/production-briefing.yml` template preserves
the existing schedule and weekly rules, executes only reviewed installed code,
and requires `CODEX_PRODUCTION_ENABLED=1`. The credential helper restricts the
publisher PAT to the public Investo destination. Pages checks the published SHA
and retries failed/cancelled deployments while avoiding an active/successful
duplicate. Rollback and exact credential scopes are in the runtime README.

Independent review passed after fixing its Pages retry finding. Full pytest
passed **5,329 tests in 326.09s** before that workflow-only repair; its subsequent
workflow/helper regression suite passed **22 tests**, including 11 Pages state
branches. Ruff/check+format, mypy (263 sources), paid/Anthropic guards,
actionlint 1.7.12, strict MkDocs and `git diff --check` are the validation gates.

Private Environment metadata currently contains `CODEX_AUTH_JSON`,
`CODEX_SECRET_WRITE_TOKEN`, `FRED_API_KEY`, and `OPENDART_API_KEY`. The last two
were registered from existing local source configuration via stdin, without
printing values. Publishing and Telegram credentials are still missing, as are
the existing BEA/Congress/KRX source keys. The October Billing usage API returns
404 with a missing `user` scope; account scope was not enlarged. The prior
September allowance is not evidence for October. The user has been asked to
register the remaining Secrets and confirm current included usage/spending
limits. No active private production schedule or enable variable was created.

## Completion gates

- [x] Identify and repair the real Codex execution failure.
- [x] Pass real briefing dry-run and finalization with no public effects.
- [x] Observe actual credential refresh, encrypted persistence and next-job reuse.
- [x] Reuse existing Telegram and source credentials in the private Environment.
- [ ] Verify publisher credentials, included usage and spending limits.
- [x] Validate and review private production workflow and rollback.
- [ ] Stop/wait for public daily owner, then switch the schedule once.
- [ ] Verify generation, finalization, auth, public push, Telegram and Pages separately.

Steps 8 and 9 remain incomplete until their operational evidence exists.

## Existing-key reuse — 2026-10-04 KST

User correction: “텔레그램, BEA, CONGRESS, KRX 관련 키는 기존 investo에
있던거 쓰면 되는데,”. Reuse was implemented; asking the user to re-enter these
existing values was unnecessary. Exact six names: `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_BRIEFING_CHANNEL_ID`, `TELEGRAM_OPERATOR_CHAT_ID`, `BEA_API_KEY`,
`CONGRESS_API_KEY`, `INVESTO_KRX_SERVICE_KEY`.

One-use source run [37136372915](https://github.com/murphyGo/investo/actions/runs/37136372915)
at `46d4c791027c0d51b6a479d4370b8e81c14feff8` encrypted those existing values
using the destination Environment public key and libsodium sealed boxes.
No plaintext value, hash or credential-bearing diagnostics were emitted.
The consumer checked the exact source run/SHA/branch, destination, key, names
and ciphertext shape, then registered the ciphertexts to the fixed private
Environment. Metadata confirmed all six on 2026-10-03 16:19:57–59 UTC.
The encrypted artifact was deleted (`total_count=0`) and the one-use remote
branch removed. Public main's workflow was never replaced by the transfer
workflow. Codex/Claude/OpenAI auth and personal credentials were excluded.

Independent reviews found no blocker. Validation: 10 producer tests, 7
consumer synthetic branches, Ruff/format, actionlint and whitespace checks.
Source and Telegram credential registration is complete. The remaining
activation prerequisites are the dedicated publisher PAT and current Actions
included usage/spending limit confirmation; public Claude remains active.
