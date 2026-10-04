# Session Log: 2026-09-22 — u145 Step 4 resume and repair

## Scope and preserved work

The user asked to continue the unfinished public sector dashboard. The active step remains
Step 4 viewport acceptance. The implementation was transferred from
`.tmp/u145-exact-20260909` into `.tmp/u145-resume-20260922`, branch
`codex/u145-resume-20260922`, based on current `origin/main`
`c286f5003973c3d7a5fc0c7db2eeda0e6e9bb64c`.

All 42 source-worktree files were preserved byte-for-byte, verified against a SHA-256 manifest.
Three-way integration retained current-main Codex redaction entries, development/operations
dependencies, and audit history while adding the recovered sector extra and Step 1–4 changes.
Conflicts in `pyproject.toml`, `uv.lock`, and `aidlc-docs/audit.md` were resolved without
overwriting unrelated main work. `uv lock --check --offline` passed.

## Repairs

An independent code review reproduced two medium-severity defects:

1. Complete sector records collected `missing_reason=None` as if it were a missing-data reason,
   making all ten normal rows display `사용 가능 · 일부 지표 부족`. The renderer now considers
   only actual missing reasons. Warming and unsupported-sector labels retain their contracts.
2. A cleanup failure after partial or complete backup deletion could return `recovery_failed`
   while retaining the newly promoted pair. Once destructive cleanup starts, a failed promotion
   now re-stages the verified previous projection and writes its recovery marker before rollback.
   Recovery uses the already pinned directory descriptors and retains the original failure.

Four initial regression cases failed before the fixes. The final tests additionally interrupt
rollback after restoring Markdown but before restoring JSON, proving that the new durable backup
can recover a mixed pair. Coverage includes partial backup removal, complete backup removal, and
marker removal, each with and without the second interruption: six storage cases plus one
availability case. The independent reviewer approved both fixes and the final test coverage with
no remaining findings in the reviewed scope.

## Validation

- Full final repository regression: **5,501 passed in 583.20 seconds**, exit 0.
- Repaired Step 4 slice: 40 passed before the three second-interruption cases were added;
  the final full run includes all 43 renderer/store cases and all seven new regressions.
- Ruff check and format: passed; 605 files already formatted.
- Strict mypy: passed on 269 source files.
- No-paid API guard: passed.
- Anthropic SDK, curated asset, and image-store guards: passed.
- Five synthetic preview states: strict MkDocs build and pair/static HTML validation passed.
- Material CSS and exact rendered light/dark image-pair contracts: passed.
- Original recovery-worktree preservation: all 42 hashes unchanged.
- `git diff --check`: passed.

The preview evidence is `.tmp/u145-viewport-check/evidence.json`; its renderer hash matches the
fixed source. It deliberately records `viewport_acceptance=NOT_EXECUTED`. Preview pages cover
fresh, eight-sector partial, warming, insufficient-history, and stale inputs. Generated pages
remain isolated under the ignored preview directory.

Full-suite output is `.tmp/resume-evidence/pytest-full.log`. The tracked/untracked scope and
content hashes are retained in `.tmp/resume-evidence/final-scope.json`. Source hashes were
checked after the run to confirm that the validated Python files did not change during it.

## Browser blocker and activation boundary

Browser startup failed before discovery because the session's configured service file
`/Users/user/.codex/plugins/cache/openai-bundled/browser/26.903.61454/scripts/browser-service.mjs`
is absent. The cached bundle is `26.814.41407`. The official Chrome native-host diagnostic also
returned `exists=false`, `correct=false` for `com.openai.codexextension.json`.

The Browser skill's `docs/chrome-troubleshooting.md` says: "Do not install or repair the native
host yourself." It requires plugin reinstallation through the app UI. The user was asked to
reinstall Browser and restart the app/Chrome while independent integration and validation
continued. No substitute runtime or native-host file was created.

Actual 390×844 and desktop layout, clipping, contrast, and readability remain unverified.
Step 4 remains open. Step 5 production-adapter probes and Step 6 schedule/Pages activation have
not started. This session makes no live HF request, commit, push, public-sector write,
navigation change, deployment, or Telegram send.

## Resume

Use the new worktree `.tmp/u145-resume-20260922`. After Browser is restored, rebuild and serve
the isolated preview, then inspect all five states on mobile and desktop in both themes:

```sh
uv run --frozen --extra dev --extra docs --extra sector python .tmp/u145-viewport-check/prepare.py
.venv/bin/python -m http.server 8145 --bind 127.0.0.1 --directory .tmp/u145-viewport-check/site
```

Start at `http://127.0.0.1:8145/u145-preview/fresh/`. Only actual successful viewport evidence
can close Step 4 and permit the Step 5 implementation/probe sequence.
