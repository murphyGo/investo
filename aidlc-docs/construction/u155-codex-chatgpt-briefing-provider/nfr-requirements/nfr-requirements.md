# u155 — NFR Requirements

**Status**: Approved for implementation — user “구현까지 진행시켜”, 2026-09-09. Live runtime qualification remains pending.
**Parent contracts**: Approved FD R1–R14; AC-155.1–AC-155.12.

## Measurable requirements

| ID | Contract and acceptance evidence | AC |
|---|---|---|
| N155-01 | Unset/blank provider preserves Claude behavior, runner injection and parser; Codex package/login/model are not required in Claude mode. | 1, 2 |
| N155-02 | One immutable config and auth session per run. Codex CLI calls never overlap, including cancellation cleanup. Pin private segment concurrency to 1; adapter lock protects other callers. | 2, 5, 8 |
| N155-03 | Keep existing retry counts/backoffs and per-segment budget. Lock wait, subprocess time and cleanup consume the applicable remaining deadline; neither stage gets a new shared allowance. No extra provider retry loop. | 8 |
| N155-04 | Private job cap 240 minutes; supervisor cap 225 minutes; no generation past supervisor minute 210. Bound each attempt by the minimum remaining call/segment/run deadline. All child processes terminate before auth persistence or lock release. | 5, 8, 12 |
| N155-05 | Only managed ChatGPT login is accepted. Explicit model, clean config and official provider; API key, ambient profile/custom endpoint and interactive login fallback are rejected. | 3, 12 |
| N155-06 | No model tools for shell, filesystem, web, apps, MCP, plugins or delegation. Read-only sandbox and prompt instructions alone do not satisfy this. Verify effective pinned-CLI tool surface with adversarial synthetic input before a live credential run. | 7, 12 |
| N155-07 | CLI child receives only explicitly allowed runtime variables and dedicated auth location. Writer, publish, Telegram, source, GitHub runner credentials and parent HOME/config are absent. Raw prompt/CLI events/stderr never reach logs or public output. | 3, 7 |
| N155-08 | Auth JSON is a regular non-symlink UTF-8 file, nonempty and strictly below 48 KiB; validate managed-auth schema before restore/write-back. Private directory mode 0700, file 0600; atomic same-directory replace. Never use auth hashes/token/account IDs as telemetry. | 4, 7 |
| N155-09 | Restore only job-start Environment Secret. After all CLI activity quiesces, validate latest file and persist it before first public effect. Changed auth is saved even when generation fails. Unchanged valid auth may return unchanged; never overwrite with a stale seed. | 4, 5, 6 |
| N155-10 | Secret API persistence has a 60-second overall deadline, at most 3 attempts per operation, per-request timeout at most 10 seconds and backoff 0/2/8 seconds clipped to deadline. Retry transport/429/5xx only; honor Retry-After only within deadline. No redirects to another host or raw response-body diagnostics. | 4, 6, 8 |
| N155-11 | Checkpoint failure blocks push/public notification/Pages and returns nonzero. A later cleanup attempt cannot retroactively permit publication in that run. Finally repeats persistence only if needed; invalid/missing current auth never replaces the Secret. | 4, 6 |
| N155-12 | Preserve finalizer, numeric/trust/link/disclaimer gates, sealed bytes and usable siblings. Public destination and explicit publication paths are fixed; no whole-checkout copy or rerun to reconstruct a sealed result. | 9, 10 |
| N155-13 | Reviewable receipt contains only date/run/code SHA/provider/model and separate generation/auth/push/notification/Pages status/duration. Reusable reasons are enumerated, never arbitrary exception text or model output. | 6, 7, 11 |
| N155-14 | Initial workflow is manual dry-run. Same auth stream cannot run locally or in another repository. One schedule owner after controlled cutover; rollback waits for the current run before switching. | 5, 11 |
| N155-15 | Before activation, prove CLI/model/account access, private Environment support, refreshed auth in the next job, realistic run duration and affordable Actions/subscription usage. No automatic paid fallback, upgrade or claim of uninterrupted auth availability. | 12 |
| N155-16 | Codex output collection is bounded: at most 4 MiB each for final UTF-8 text and retained diagnostic/event bytes per call; stop overflowing subprocess and discard output. Only validated final text enters existing parsers. No raw overflow payload in exceptions. | 7, 8, 9 |

The 4 MiB collection ceiling is an operational safety bound, not a new report
length target. Preserve tighter existing prompt/parser/document limits.
Choose a pinned CLI mode that separates the final answer from events; event
inspection stays private and in bounded memory. Disabling tools prevents
actions; detecting an event afterwards is only an additional acceptance check.

## Time accounting and capacity

Baseline source sets 1,800 seconds per call, 3,900 seconds shared for US and
5,700 seconds shared for each domestic/crypto run; default wrapper values
are 120/300 seconds. Three sequential segment ceilings sum to 15,300 seconds
(255 minutes), already exceeding the 240-minute job cap before setup/data
work. Therefore these limits cannot all be exhausted in one successful job.

Codex's private workflow explicitly sets
`INVESTO_SEGMENT_GENERATION_CONCURRENCY=1`. Existing market semaphore
admission remains outside each market's own generation budget; the absolute
run cutoff includes that wait. The adapter's auth-lock wait counts against
its request/segment budget. Record the two waits separately and do not
double-charge elapsed time. Keep Claude's existing semantics unchanged.

Start the monotonic supervisor clock before collection. Stop admission and
terminate generation by minute 210; remaining 15 minutes are reserved for
auth checkpoint, existing finalization/publication and cleanup. If time is
insufficient to finish safely, exit nonzero and preserve auth. Supervisor
SIGTERM is followed by process-group cleanup, at most 5 seconds graceful
termination plus 5 seconds forced reap. The 240-minute Actions limit is an
outer emergency cutoff; reserve setup time through a 15-minute setup cap.
An outer runner kill cannot guarantee finalizers run.

The 225-minute supervised allowance includes publication, any explicit Pages
dispatch, cleanup and receipt work. A later workflow step does not receive a
fresh allowance; pass/check the remaining deadline for those operations.

Qualification records durations for setup, collection, auth-lock wait,
each generation stage, checkpoint, finalization, push and notifications.
Use representative successful, partial and retrying runs; do not label a
single smoke test as a latency percentile or throughput result.
Estimate monthly runner minutes from measured duration and the actual
schedule/manual-retry count, then compare against the account's remaining
included allowance and configured spending limits. Plan/allowance is unknown.

## Failure and recovery acceptance

| Injected condition | Required outcome |
|---|---|
| Old synthetic token rotates; model fails or times out | Save valid new file; generation stays failed; no stale seed rewrite |
| Auth lock held until deadline | No child launch; bounded failure; existing stage budget charged |
| Cancellation while child still runs | Terminate/reap before lock release and reading auth for persistence |
| Writer permission denied or API unavailable | Nonzero, no new public side effect; sanitized private status |
| Missing/truncated/symlink/oversized final auth | Preserve server's prior Secret; recovery required |
| Child output contains synthetic old/new token leaves | Drop/redact before any logging, parser/public surface or artifact |
| Malicious instructions ask for files, web or other tools | No tool exposure/execution; acceptance fails if any action occurs |
| Push succeeds but notification/cleanup fails | Record actual push separately; no false “nothing published” receipt |
| Same-date rerun or remote main advances | Existing duplicate/push rules; current archive lineage; explicit staged paths |

A checkpoint success proves the encrypted write request succeeded; the
next serialized job proves continued login access. Neither guarantees
indefinite validity. Manual re-registration uses a dedicated login and never
edits/copies the personal interactive Codex profile.

## Verification ownership

Unit/fake-clock tests cover N155-01–11/13/16; workflow contract tests cover
private/event/environment/concurrency/dependency constraints; local
two-repository integration covers N155-12/14. Partial PBT applies to pure
config/auth parsing and serialization, not live service behavior.
Run existing quality/publication suites for both providers, all appropriate
repository gates, independent review and requirements cross-check.
N155-15 and real queued-job refresh behavior require separate private
operational evidence; synthetic tests cannot close them.

## Sources

- [Codex CI authentication](https://learn.chatgpt.com/docs/auth/ci-cd-auth):
  private trusted automation and serialized refresh/persistence lifecycle.
- [GitHub Secret timing and limits](https://docs.github.com/en/actions/reference/security/secrets):
  Environment read timing and 48 KB size ceiling.
- [Private environment features](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments):
  supported account plans; account qualification remains pending.

Numeric supervisor/HTTP/output limits above are Investo design decisions,
not limits or guarantees supplied by those vendors.
