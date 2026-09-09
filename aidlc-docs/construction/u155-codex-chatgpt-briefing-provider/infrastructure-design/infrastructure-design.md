# u155 — Infrastructure Design

**Status**: Approved for implementation — user “구현까지 진행시켜”, 2026-09-09. No infrastructure provisioned.
**Prerequisite**: Private Environment Secrets supported by the owner's GitHub
plan. Account API did not return the plan; user answer is pending.

## Resource mapping

| Resource | Concrete role | Mutable state / access |
|---|---|---|
| Public `murphyGo/investo` | Reviewed code, public archive and existing Pages | No ChatGPT auth injected into public Actions |
| Proposed private `murphyGo/investo-runtime` | Trusted workflow template, locked execution SHA and private receipts | Trusted owner-controlled manual runs; schedule introduced only at activation |
| Private Environment `codex-runtime` | Job-start auth and operation credentials | Auth writer updates only its configured auth slot; explicit environment binding |
| One standard hosted Ubuntu job | Dependency setup, supervisor, cleanup and receipt | Ephemeral runner; 240-minute outer cap; no untrusted PR/fork event |
| Reviewed code checkout | Build/install exact approved full commit SHA | No implicit latest code, branch override or post-auth package installation |
| Latest public checkout | Current archive/carryover input and explicit result publication | Public origin/main fixed; no checkout-wide stage/copy |
| Temporary auth/empty model directory | Restricted CLI auth/config and empty model working root | Outside both checkouts; no cache/upload; removed after preservation |
| Existing public Pages workflow | Builds public site after confirmed publication | Explicit dispatch using public-repository authorization |

No database, object bucket, incoming service endpoint, new queue or shared
cloud service is introduced. Existing Pages, archive and notifier contracts
remain owned by their current units.

## One job and credential flow

Use one Environment-bound job so that the existing Python pipeline can
generate, checkpoint, finalize, publish and notify without transporting
internal models between jobs. The FD table's separate publishing-environment
suggestion is refined to one Environment with separate tokens; this placement
change is a proposal requiring this review.

| Name | Scope / consumer | Codex child |
|---|---|---|
| `CODEX_AUTH_JSON` | Environment only; restore helper converts to restricted auth file, then removes seed from subprocess environments | Only dedicated file, never JSON environment variable |
| `CODEX_SECRET_WRITE_TOKEN` | Private repo fine-grained `Environments: write`; trusted checkpoint helper | Absent |
| `INVESTO_PUBLIC_PUBLISH_TOKEN` | Fixed public repo `Contents: write` plus `Actions: write` for Pages dispatch | Absent |
| Existing Claude token | Required only when Claude selected; injected only into Claude runtime path | Absent |
| Existing source secrets | Existing source clients in trusted parent | Absent |
| Telegram secrets | Existing notifier after publication, or approved private operator alert | Absent |

These are application-level stage restrictions inside a trusted supervisor,
not separate-OS-user isolation. The model cannot receive parent credentials
or tools that inspect the parent. Keep publish credentials out of persistent
Git configuration and argv. Bind credentials only to the relevant helper's
operation; the ordinary child environment is an explicit allowlist.
The writer's GitHub permission can update other environment settings/secrets
in that selected repository; fine-grained PAT permissions are not a
per-secret-name ACL. The helper fixes repo/environment/name and rejects input
overrides. Scope and token expiry are reviewed before registration.

Initial dry-run has no publish-token or Telegram-send-secret injection.
Provider-aware dry-run preflight must permit this without fake production
secrets, and tests must exercise the real pipeline entrypoint. Auth write-back
is still necessary in a dry-run because generation can rotate the login.

## Secret freshness and workflow admission

Workflow-level concurrency group: `investo-codex-auth-v1`, fixed across
dates, branches, provider choices and manual/scheduled invocations.
`cancel-in-progress: false`. Bind the job to the fixed Environment; validate
the repository is private, expected owner/repo/default branch and a trusted
manual or scheduled event. No `pull_request`, `pull_request_target` or
untrusted workflow input interpolation.

Check through Environment Secret metadata that `CODEX_AUTH_JSON` exists
in the bound environment, not merely a same-name repository fallback.
Failure or insufficient metadata permission fails preflight. Secret values
are never read back through the API. Runtime authorization must remain
available long enough to persist refreshes; token-expiry errors have a
recovery receipt rather than a leaked response body.

The fixed lock admits one running workflow; Environment Secrets are resolved
at job start after admission. Actions concurrency does not promise FIFO or
execution of every queued run. Cross-repository/local reuse is forbidden
because that lock cannot serialize it. A login is dedicated to this stream.

## Reviewed code versus latest public data

1. Checkout runtime control files from the trusted private default branch.
2. Checkout public execution code at a reviewed 40-character SHA; verify
   exact HEAD. Pin dependency/action versions during implementation.
3. Build and install the approved package non-editably in a dedicated virtual
   environment from its lock. Invoke its absolute Python executable with
   isolated import behavior; unset PYTHONPATH. Do not run `uv run` from the
   latest publication checkout, which could resolve that checkout's project.
4. Independently checkout latest public origin/main with credentials not
   persisted. Use this directory as pipeline cwd, since
   `publisher.paths.ARCHIVE_ROOT` and related site paths are relative.
   Verify import provenance still points to approved installed code.
5. Treat current watchlist, archives and image manifests as data accepted
   only by their existing parsers; never execute scripts/hooks/config code
   from the latest checkout. Use trusted helper paths from the reviewed code.
6. Disable local Git hooks/ambient credential helpers; verify fixed remote
   identity and explicit staged file paths before commit/push. The public
   checkout can rebase its generated changes onto newer public main through
   existing Git policy; execution SHA stays fixed.

Local integration tests use two bare repositories and different approved-code/
latest-archive commits. Assert execution identity, current carryover reads,
allowed staged paths, unrelated dirty-file exclusion, push conflicts and
same-date reruns. Do not reset archives to the reviewed code's historical state.

## Dependency setup and retention

Setup finishes before restoring credentials. Install only locked Python/CLI
dependencies and pinned Actions; any Linux/system package requirements must
be known before auth is present. The setup cap is 15 minutes.
Cache only explicit dependency paths if cache is used; never cache HOME,
CODEX_HOME, runner temp, either entire checkout or model transcripts.
Initial template can omit caches to simplify credential qualification.

The private receipt contains enumerated status and timing metadata only.
Do not upload generated raw prompts, CLI output, auth files or a workspace
bundle. Public results go through the existing publisher, not Actions
artifacts. Receipt retention is short and explicit (proposed seven days).

## Account features and operational gates

2026-09-09 read-only evidence:

- `murphyGo/investo` is public.
- `gh api user` returned `plan: null`; it establishes no account tier.
- Private candidate repository lookup returned 404; creation/access unresolved.
- GitHub documentation requires Pro/Team/Enterprise for private Environment
  Secrets. Do not assume private required-reviewer/wait-timer protection is
  available on Pro/Team; this design does not depend on it.

If the account is Free, this exact private-Environment design is not
deployable as proposed. Keep the local implementation/template conditional;
review an alternative or an explicitly authorized plan change. Do not use
repository-secret queue snapshots as an invisible substitute.
The proposed repository name, actual environment eligibility, dedicated login,
exact model, token scopes and minute/spending allowance are checked before
live provisioning or activation.

Sources:
[GitHub environment features](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments),
[Secret read timing](https://docs.github.com/en/actions/reference/security/secrets),
[Environment Secret API](https://docs.github.com/en/rest/actions/secrets#create-or-update-an-environment-secret).
