# u155 — Tech Stack Decisions

**Status**: Approved for implementation; local CLI/runtime implementation added. Credentialed Linux qualification pending.

| Decision | Selection and reason | Verification |
|---|---|---|
| Generation integration | Existing Python CLI subprocess seam and two-stage parser; neutral config module, Claude compatibility wrapper retained | Same fixtures through both providers; no new SDK/model service |
| Codex distribution | Official Codex CLI, exact version locked in private template; 0.153.4 native release is pinned with verified digest; Linux runtime qualification remains pending | Verify official package/version/integrity and Linux behavior during implementation |
| Invocation | Argument list, stdin prompt, explicit model, empty work directory, final-answer-only adapter | Local 0.153.4 help confirms stdin, ephemeral, config/rules isolation and last-message options |
| Configuration | Dedicated CODEX_HOME, file credential store, forced ChatGPT login, known config overrides; no user profile or project instruction inheritance | Strict config parsing plus effective tool/config qualification on exact version |
| Tools | Disable shell/unified execution, web, local images, apps/MCP/plugins/hooks, memory/skills and agents as supported by pinned CLI | No blanket “disable all” switch has been established; inspect effective tools, reject unsupported configuration |
| Authentication | CLI owns refresh; Python operations helper validates and atomically restores/saves | Opaque credential payload; typed safe outcomes; old/new synthetic token tests |
| Secret encryption | GitHub Environment Secret API with an audited libsodium sealed-box binding (PyNaCl, exact lock entry during implementation) | Known public-key fixture, encrypted request shape; no hand-written cryptography |
| HTTP | Reuse existing HTTP client dependencies where appropriate; deadline and redirect restrictions belong to operations helper | Fake transport for 201/204, transient, permission and timeout cases |
| Runner | Standard GitHub-hosted Ubuntu runner, versioned label selected in template; existing Python/uv stack; Node version meeting pinned CLI requirements | Auth restored only after dependency setup; no self-hosted service introduced |
| Observability | Existing safe stage status plus private receipt; bounded CLI capture | No auth/session directories, transcripts or raw prompts as artifacts/caches |
| Publication | Existing in-process finalizer/publisher/notifier with a pre-publication auth callback | One finalizer and one explicit Git publication path |

## CLI settings to qualify

Local help and the official reference establish candidate controls:
`--ephemeral`, `--ignore-user-config`, `--ignore-rules`,
`--strict-config`, `--sandbox read-only`, `forced_login_method="chatgpt"`,
`cli_auth_credentials_store="file"`, `features.shell_tool=false`,
`features.unified_exec=false`, `agents.enabled=false`,
`web_search="disabled"` and `tools.view_image=false`.
These are a starting point, not a claim that all tools are disabled.
Local feature discovery shows additional app/browser/computer/plugin/hook/
agent capabilities. Qualify all relevant registered tools, instruction
discovery and optional extensions on the actual Linux package.

Use an empty work directory outside both checkouts. The child receives an
isolated HOME as well as a dedicated CODEX_HOME; passing only CODEX_HOME
does not prove all host instruction discovery is disabled. Do not overwrite
the parent process's HOME/CODEX_HOME or invoke login/logout in qualification.
The trusted supervisor has broader filesystem access than the model.
The threat boundary is hostile market text, not a compromised CLI binary or
runner administrator; tool disabling and dependency pinning are necessary.

Implementation Step 3 must stop live credential qualification if effective
tool restrictions cannot be proved. Resolve with a reviewed CLI/version
choice; do not weaken R4 or switch to an API key silently.

## Environment layout refinement for review

The FD secret table suggested a separate private publishing environment.
A GitHub job binds one Environment, while the current pipeline generates,
finalizes, publishes and notifies within one process. This design proposes
one `codex-runtime` Environment and one trusted job, with separate narrowly
scoped writer and publisher credentials held by the supervisor.
Neither credential enters the Codex child. Only the existing publication
boundary receives public-write capability after successful auth checkpoint.

This changes the proposed Secret placement, not the approved child-credential
or persistence-before-publication contracts. It avoids a new cross-job bundle
format and repeated finalization. The proposal requires this NFR/Infrastructure
approval; do not represent the single-Environment refinement as already
approved. Initial dry-run does not inject publisher or Telegram send secrets.

## Primary references

- [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference):
  authentication/file-store and individual feature/tool controls.
- [Codex non-interactive CLI](https://learn.chatgpt.com/docs/non-interactive-mode):
  stdin and final-output integration.
- [GitHub Environment Secrets API](https://docs.github.com/en/rest/actions/secrets#create-or-update-an-environment-secret):
  sealed-box encryption, environment-write permissions and success responses.

Local evidence: `codex --version`, `codex exec --help` and
`codex features list` on 2026-09-09. No auth file read or model invocation.
