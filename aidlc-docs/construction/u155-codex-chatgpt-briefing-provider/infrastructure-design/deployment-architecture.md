# u155 — Deployment Architecture

**Status**: Approved; manual template and local implementation created. Remote provisioning and activation pending.

## Runtime sequence

```mermaid
sequenceDiagram
    participant A as Private Actions job
    participant S as Trusted supervisor
    participant C as Codex CLI
    participant E as Environment Secret API
    participant P as Existing public publisher
    A->>A: Fixed concurrency admission and job-start secrets
    A->>A: Pin code, install dependencies, checkout current archive
    A->>S: Restore dedicated auth and freeze provider/model
    loop Existing selected markets and two generation stages
        S->>C: Serialized stdin prompt, minimal env, tools disabled
        C-->>S: Final text; CLI may rotate local auth
    end
    S->>S: Reap CLI processes and validate latest auth
    S->>E: Encrypt and persist changed valid auth
    alt Valid unchanged auth or successful persistence
        S->>P: Existing finalization and publication eligibility
        P->>P: Explicit paths, public push, then notification/Pages policy
    else Invalid auth or failed persistence
        S->>S: Nonzero status; block public effects
    end
    S->>S: Finally preserve if needed, clean temp, write safe receipt
```

In dry-run the publisher path performs its existing local validation/write
behavior but cannot commit/push/send/dispatch. The auth checkpoint still runs.
No model call may start after the checkpoint; otherwise the persisted session
could become stale before publication.

## Checkpoint and outcome contract

Insert an optional lifecycle callback at the existing orchestrator's
generation-to-publication boundary. Claude's callback is a no-op; Codex's
trusted helper waits for all child activity to stop, validates the latest
file and persists changed auth. Existing finalization stays inside its
current publication stage. No second parser, public model or finalizer.

The callback must execute for unsegmented and segmented paths, including
partial generation. A generation failure that skips publication still reaches
the outer finally preservation path. Cancellation and output overflow must
terminate/reap the child process group before reading auth; killing only the
launcher or releasing the lock early is insufficient.

On successful checkpoint, freeze the auth outcome for this publication
attempt. If checkpoint fails, the finally path may restore durable auth but
cannot resume publication; a later run follows the normal rerun policy.
Avoid duplicate writes by tracking the last persisted bytes in memory only.
Never log a credential fingerprint. Keep original Secret intact for malformed
final files. Strong runner kill is explicitly outside cleanup guarantees.

The auth helper reads the environment's encryption public key and uploads
only a sealed-box ciphertext to the fixed auth slot. Success is the documented
201/204 status; use bounded retries/deadline from N155-10. Do not follow
redirects with writer authorization. Remove plaintext temp material after the
last required preservation attempt.

## Manual qualification before activation

| Order | Concrete evidence required | Public side effects |
|---|---|---|
| 1 | Local implementation, synthetic auth/timeout/CLI restrictions, two-repository tests, full quality gate, independent review and cross-check | None |
| 2 | Review private repo/name, account Environment support, token scopes/expiry, exact CLI/model, pinned code SHA and spending configuration | None |
| 3 | Provision approved private workflow; register dedicated automation auth via file-to-secret helper; never paste tokens into chat | Private configuration only |
| 4 | Run manual dry-run with source data and Codex; record finalization/auth/time/quota status separately; assert public refs and send counts unchanged | None |
| 5 | Run a second serialized job from saved auth; qualify refresh/write-back with dedicated auth when a real refresh occurs | None |
| 6 | Exercise queued-job freshness, failure after rotation, write denial and recovery in a controlled private test environment | None |
| 7 | Review run durations, remaining included minutes and model access before enabling any schedule | None |

A second run without actual refresh proves reload/access, not token-rotation
durability. Use synthetic rotation tests plus a real observed dedicated-session
refresh; do not manipulate token contents or an interactive personal login to
manufacture that evidence.

Initial workflow inputs: provider choice (default Claude), validated target
date and explicit model for Codex. Dry-run is fixed on in the initial template.
Do not expose arbitrary repository URLs, execution SHA overrides, command
strings or auth-secret names as dispatch inputs. The reviewed execution SHA
is trusted runtime configuration.

## Cutover and rollback

Cutover is a separately recorded operation after local and private dry-run
acceptance. Inspect any active public and private daily runs. Stop the public
daily schedule owner and await its completion before enabling the private
schedule. Verify no in-flight run holds the dedicated auth elsewhere.
Use the existing market calendar/times; do not introduce a second cron owner.

After the first bounded production run, inspect each result separately:
generation, finalization/usable siblings, auth persistence, public commit SHA,
Telegram and explicit Pages run. An exit code or `publication_committed`
flag alone is insufficient to claim the whole operation succeeded.

Rollback stops private scheduling and waits for running auth/publish activity
to finish, then restores the public Claude daily owner. Confirm the date's
public commits and notification history before rerunning. A push completed
before a later failure remains published. Follow current rerun behavior; do
not promise exactly-once Telegram delivery where the existing system has
no durable delivery ledger.

On auth recovery, pause the private stream, inspect safe failure reasons,
create a new dedicated login only after authorization, and register it in the
same Environment slot. Never automatically replace it with repository auth,
an API key or personal interactive session.

## NFR mapping

N155-01/05/06/07/16 map to the provider adapter and clean CLI process;
N155-02/03/04 to private concurrency, segment configuration, lock/deadline
and supervisor; N155-08/09/10/11 to auth helper/callback/finally;
N155-12 to the existing finalizer/public checkout; N155-13 to safe receipts;
N155-14/15 to qualification and cutover. All twelve ACs remain unchanged.

No runtime, workflow activation, Secret registration, live generation,
public push, notification or Pages dispatch was performed to write this design.
