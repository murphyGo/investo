# u155 — Domain Entities

**Status**: Functional Design approved, 2026-09-09 KST; runtime classes are
not implemented.

| Entity | Fields / responsibility | Validation / ownership |
|---|---|---|
| LlmProvider | claude, codex | closed set; run-level immutable choice |
| LlmExecutionConfig | provider, optional explicit model, existing generation policy | Codex requires model; no credentials; neutral shared owner |
| LlmSession | config, shared Codex call lock, lifecycle state | one per run; no cross-provider reuse; created by runtime boundary |
| LlmCallRequest | existing prompt, stage, remaining timeout | stdin only; prompt never includes credentials |
| SubprocessOutcome | existing stdout, stderr, returncode, elapsed_s | reuse current type; diagnostic filtering before exposure |
| AuthCheckpointOutcome | not_applicable, unchanged, persisted, failed; bounded reason | no token, user identifier, raw body, or secret fingerprint |
| PublicationEligibility | existing finalized bundle eligibility plus auth checkpoint | only orchestrator combines conditions |
| ExecutionReceipt | run/date, code SHA, provider/model, generation/persistence/publish/notify/Pages statuses | private operational evidence; public payload unchanged |

Authentication file contents remain opaque credentials of the CLI/operations
boundary. They do not become Pydantic public models, briefing fields, facts,
raw_metadata, source outcomes, notification DTOs or visual provenance.

## Relationships

One execution config determines all stage requests. One Codex session serializes
all requests sharing the same auth file, including calls for different markets.
Each request returns the existing subprocess outcome to the existing parser.
The orchestrator combines finalized public eligibility with checkpoint success.
The execution receipt records results without changing existing public statuses.

## Identity and lifetime

- Provider/model are selected once at process bootstrap.
- An auth file belongs to one serialized automation stream.
- The auth file is restored at job start; only the CLI rotates its tokens.
- Successful persistence refers to the same private environment/secret slot.
- Auth material is removed from the runner after the last preservation attempt.
- Run/date/code SHA are traceability metadata, never substitutes for a secret.
- A same-date rerun is a new execution but must obey current publication rules.

## Compatibility

Keep `ClaudeRunner`, `call_claude_code` and existing positional/keyword
contracts usable until callers migrate. A shared provider runner can replace
the internal dispatch without rewriting the input selection or finalizer.
Default construction through the old API must invoke only Claude.
Tests inject execution results without a real login, network or npm install.
