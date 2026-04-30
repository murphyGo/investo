# u6 infra/CI — Code Generation Summary

**Date**: 2026-05-01
**Stage**: Code Generation (final stage for u6 infra/CI; FD + NFR Requirements both N/A per execution-plan — YAML/config only, no new Python source code)
**Status**: ✅ COMPLETE
**Stories closed**: US-005 (cron half — completes the orchestrator's surface), US-003 (Pages half — completes the publisher's surface)

**With u6 closed, all 6 units of the project are complete.** Only global Build & Test remains.

---

## Files created / modified

### YAML / config (the unit's primary deliverables)

| File | LOC | Role |
|------|----:|------|
| `.github/workflows/daily-briefing.yml` | 130 | Cron schedule + `workflow_dispatch` w/ `target_date` input + `python -m investo` runner. `timeout-minutes: 12` per AC-001-4. `permissions: contents: write` (least privilege). Concurrency group serializes manual+cron fires. Comprehensive YAML comment header documents schedule, KST↔UTC mapping, KST-no-DST since 1988, secrets, and exit-code mapping. (Steps 1, 2) |
| `.github/workflows/pages.yml` | 111 | Push-on-main + workflow_dispatch trigger w/ `paths:` filter (saves GHA minutes by skipping unrelated pushes). Two-job split: `build` (`mkdocs build --strict` + upload-pages-artifact) → `deploy` (`actions/deploy-pages@v4`, environment-bound for Pages URL surfacing). Atomic deploy preserves prior site on build failure (DoD). (Step 3) |
| `mkdocs.yml` | 107 | Material theme + Korean tokenization (search plugin `lang: [ko, en]`; pinned floor 9.5 for KO support). `docs_dir: site_docs/`. 3-entry nav (Home / About / Archive → `archive/index.md`). Markdown extensions for tables, footnotes, admonitions, ToC permalinks. `site_url` deliberately omitted to prevent fork/staging URL leakage. `--strict` flag enabled at CLI level (in pages.yml) so local `mkdocs serve` tolerates drafts. (Step 4) |
| **YAML subtotal** | **348** | 3 workflow / config files |

### Markdown / site source

| File | LOC | Role |
|------|----:|------|
| `site_docs/index.md` | 32 | Korean landing page. 7-section structure overview, free-tier data-source policy, archive + Telegram channel pointers, prominent disclaimer block (NFR-004 cross-unit). (Step 4) |
| `site_docs/about.md` | 49 | Korean about page. 운영 원칙 (월 운영비 $0 / 자동화 우선 / 공개 + 영구 보관), 데이터 소스, 기술 스택, 면책조항 quote, GitHub source link. (Step 4) |
| `archive/index.md` | 13 | Korean placeholder for the pre-first-cron state — replaces itself with the daily briefings as the bot writes them. (Step 4) |
| `archive/.gitkeep` | 0 | Ensures `archive/` exists in git before first cron write (DEBT-026: redundant alongside `archive/index.md` — flagged for cleanup). (Step 1) |
| `site_docs/archive` | symlink | Tracked symlink → `../archive` (mode 120000). Surfaces `archive/YYYY/MM/...md` under `site_docs/archive/...md` for mkdocs without a post-process step. **Critical fix C1 (Step 6)**: was untracked initially; without `git add` the very first CI build would have failed `mkdocs build --strict` on a fresh checkout. (Steps 4, 6) |
| **Markdown subtotal** | **94** | 3 markdown files + 1 symlink + 1 keep-alive |

### Python (side-quest surfaced by u6's needs)

| File | LOC change | Role |
|------|-----------:|------|
| `src/investo/__main__.py` | +56 | Added `_TARGET_DATE_OVERRIDE_VAR` constant + `_resolve_target_date_override()` helper + `target_date_override` forwarding to `run_pipeline`. Closes the gap where the YAML's `workflow_dispatch + target_date` input would have been a non-functional UI element. Whitespace-tolerant; fail-fast on malformed values (won't silently roll back to cron default — that would publish for the wrong date entirely). |
| `tests/unit/orchestrator/test_main.py` | +152 / **+15 tests** | Override coverage: absent → None, empty/whitespace → None, valid ISO → date, whitespace strip, 6-parametrized malformed → exit 1, malformed → boot-alert, 3 direct unit tests of the helper. |
| **Python subtotal** | **+208** | 0 new src/test files; 1 src extended + 1 test extended |

### Project metadata

| File | LOC change | Role |
|------|-----------:|------|
| `pyproject.toml` | +9 | `[project.optional-dependencies] docs = ["mkdocs-material>=9.5"]`. Pin floor 9.5 chosen for Korean-friendly default search tokenization. Inline comment ratifies the dev/docs split (NFR-002 minimal-runtime — runtime install carries only pydantic / httpx / defusedxml / bleach). (Step 1) |
| `CONTRIBUTING.md` | +110 | New "Operator runbook (u6 infra/CI)" section: GitHub Secrets table, cron schedule (UTC↔KST), manual `workflow_dispatch` trigger + `target_date` input semantics, US public holiday Q3=A recovery flow, Pages deploy semantics. Plus a docs-build sub-block in the existing quality-gate section. (Step 5) |
| `.gitignore` | +3 | Added `/site/` (mkdocs build output; published as Pages artifact, never checked in). (Step 4) |

### Total scope

- **YAML / config**: 348 LOC across 3 files
- **Markdown**: 94 LOC across 3 files (+ 1 tracked symlink + 1 .gitkeep)
- **Python (side-quest)**: +208 LOC (1 src extended w/ helper + tests; closes u5→u6 surface-area gap)
- **Project metadata**: +122 LOC (pyproject + CONTRIBUTING + .gitignore)
- **Total: ~770 LOC across 11 modified/created files**, 0 new source files in `src/investo/`, 0 new test files

---

## DoD verification

Per `aidlc-docs/inception/application-design/unit-of-work.md` u6:

| DoD item | Verdict | Evidence |
|----------|---------|----------|
| cron 평일 KST 07:00 (UTC 22:00 전일) + 토 09:00에 실행 | ✅ | `daily-briefing.yml:60-63` — two cron entries `0 22 * * 0,1,2,3,4` (Sun-Thu UTC 22:00 = Mon-Fri KST 07:00) + `0 0 * * 6` (Sat UTC 00:00 = Sat KST 09:00). Sub-agent review verified the day-of-week arithmetic. |
| `python -m investo`가 GitHub Secrets로 인증되어 동작 | ✅ | `daily-briefing.yml:117-129` — 5 secrets injected via `env:` block per AC-007-1. `__main__._validate_env` rejects missing or whitespace-equal chat IDs (CLAUDE.md #5) before constructing dispatchers. |
| commit 후 자동으로 Pages 빌드/배포 | ✅ | `pages.yml:31-41` — `push: { branches: [main], paths: [archive/**, site_docs/**, mkdocs.yml, pyproject.toml, .github/workflows/pages.yml] }`. Bot's `archive/...md` writes always trip the filter. |
| 빌드 실패 시 기존 사이트 유지 | ✅ | `pages.yml` two-job split (`build` → `deploy with needs: build`) + `actions/deploy-pages@v4` atomic swap. Failed `mkdocs build --strict` blocks `deploy` → live `gh-pages` untouched. Documented at `pages.yml:6-11` and `CONTRIBUTING.md:294-295`. |

All 4 DoD items pass. **u6 unit-of-work definition fully satisfied.**

---

## Module-boundary verification (CLAUDE.md #3)

u6 is **YAML / config only — no Python imports** in workflow YAML or markdown.

The side-quest `__main__.py` extension reads `os.environ["INVESTO_TARGET_DATE"]` and calls `date.fromisoformat()` — both stdlib. No new cross-module import; existing `investo.notifier` / `investo.orchestrator` imports were already in place from u5. Verified.

---

## NFR / project-rule traceability

| Rule | Verdict | Evidence |
|------|---------|----------|
| **NFR-001** (≤10 min wall-clock) | ✅ | `daily-briefing.yml:80` — `timeout-minutes: 12` per AC-001-4 (10-min design budget + 2-min safety margin). |
| **NFR-002** (zero-cost / no paid APIs) | ✅ | `pyproject.toml` `[project] dependencies` unchanged from u5 closeout (pydantic / httpx / defusedxml / bleach only). `mkdocs-material>=9.5` strictly in `docs` optional group. GHA cron + Pages on free tier. No `anthropic` / `tenacity` / `backoff` / `pandas_market_calendars` / `pandas` / `structlog` / `loguru` / `pytz` / `pendulum` / `pydantic_settings` / `respx`. |
| **NFR-003** (graceful degradation) | ✅ (cross-unit) | u5 owns the Q9=B router; u6 just wires the entrypoint. Pipeline failures surface via OperatorAlerter (Telegram 1:1) + GHA's default email alert as fallback. Documented in `CONTRIBUTING.md` operator runbook. |
| **NFR-004** (disclaimer enforcement) | ✅ (cross-unit) | u3's `verify_disclaimer` blocks publish; u6 doesn't bypass. `site_docs/index.md` + `site_docs/about.md` carry the disclaimer block at the bottom for direct site visitors who don't see the per-day briefings. |
| **NFR-007** (secrets / PII boundary) | ✅ | All 5 secrets via `env:` block; no `echo`/`set -x`/`--debug`. GHA auto-masks `secrets.*`. `_redact_bot_token` (u4) handles error-message redaction. `actor_id` is public + integer. |
| **CLAUDE.md #3** (module boundary) | ✅ | u6 YAML/config only; side-quest `__main__.py` extension uses stdlib only. |
| **CLAUDE.md #5** (chat-ID disjointness) | ✅ | `daily-briefing.yml` injects two separate secrets; `__main__._validate_env` enforces whitespace-tolerant disjointness BEFORE either dispatcher is constructed (per H2 fix from u5 Step 12). Documented in `CONTRIBUTING.md` Secrets table. |
| **FR-006** (same-day overwrite) | ✅ (cross-unit) | u3's `write_briefing` is atomic + idempotent. u6's holiday-recovery flow (`CONTRIBUTING.md:282-284`) explicitly leverages this — re-running with the same `target_date` overwrites cleanly. |

---

## Open TECH-DEBT items

### From u6 (new this stage)

| ID | Priority | Source step | Description |
|----|----------|-------------|-------------|
| DEBT-022 | Low | Step 6 review | `pages.yml` permissions at workflow level instead of job level |
| DEBT-023 | Low | Step 6 review | `daily-briefing.yml` installs `--extra dev` (pytest et al.) but never runs them — could use `--no-dev` for ~10-15s faster cold start |
| DEBT-024 | Low | Step 6 review | `astral-sh/setup-uv@v3` not pinned to SHA |
| DEBT-025 | Low | Step 6 review | `ConfigError.missing_vars` overloaded for the malformed-value case from the INVESTO_TARGET_DATE side-quest |
| DEBT-026 | Low | Step 6 review | `archive/.gitkeep` redundant alongside `archive/index.md` |
| DEBT-027 | Low | Step 6 review | Windows checkout symlink limitation undocumented |

### Cross-unit / pre-existing (unchanged)

| ID | Priority | Origin |
|----|----------|--------|
| DEBT-001 / DEBT-002 | Medium | models |
| DEBT-007 / DEBT-012 | Medium | u2 / u3 |
| DEBT-006 / DEBT-008 / DEBT-010 / DEBT-011 | Low | u2 |
| DEBT-013 | Low | u3 |
| DEBT-014 / DEBT-015 / DEBT-016 | Low | u4 |
| DEBT-003 / DEBT-004 / DEBT-005 / DEBT-009 | Low | u1 |
| DEBT-017 / DEBT-018 / DEBT-019 / DEBT-020 / DEBT-021 | Low | u5 |

**6 of 27 open items originated in u6; all 6 are Low priority.**

---

## FD-vs-implementation divergences (ratified in audit log)

Three structural deviations or ratified fixes landed during u6:

1. **Step 1.4 — `--extra docs` + `--extra dev` interaction caught early**. `uv sync --extra docs` ALONE replaces dev deps with docs deps (uv's default). Documented as a CI gotcha in CONTRIBUTING.md so contributors run `uv sync --extra dev --extra docs` for combined work. Workflows handle it correctly: `daily-briefing.yml` uses `--extra dev` (no docs); `pages.yml` uses `--extra docs` (no dev). Asymmetry is intentional.

2. **Step 2 side-quest — `INVESTO_TARGET_DATE` override**. Writing the workflow_dispatch input revealed that u5's `__main__.py` had no path to honor it. Closed during u6 Step 2 (rather than registering as a TECH-DEBT and shipping a non-functional UI element) because the gap was small (~50 LOC + 15 tests) and the alternative would degrade the operator's manual-trigger UX. Ratified in audit log under Step 2.

3. **Step 6 C1 fix — symlink tracking**. The `site_docs/archive` symlink was created with `ln -s` during Step 4 but never `git add`-ed. Without the C1 fix the very first CI run would have failed `mkdocs build --strict` on a fresh checkout (the symlink wouldn't exist). Caught by the sub-agent review (Step 6); fixed via `git add site_docs/archive` (mode 120000 confirmed). Real correctness bug caught before merge.

All three ratified in `aidlc-docs/audit.md`. No cross-unit contract was broken.

---

## Story status

- ✅ **US-005** (스케줄 실행) — closed by `daily-briefing.yml` + `__main__.py` + the orchestrator chain. KST 평일 / 토요일 cron correctly maps to the previous US trading day via u5's `resolve_target_date`. Manual trigger via `workflow_dispatch + target_date` for backfill / holiday recovery.
- ✅ **US-003** (정적 게시) — closed by `pages.yml` + `mkdocs.yml` + `site_docs/`. mkdocs-material renders the briefings at `https://murphygo.github.io/investo/archive/YYYY/MM/YYYY-MM-DD/`; failed builds preserve the prior site (atomic deploy).

---

## All 6 units now closed

| Unit | Stage status | Tests | Stories |
|------|-------------|------:|---------|
| models (foundation) | ✅ Complete | 101 (incl. PBT round-trips) | — |
| u1 sources | ✅ Complete | 252 | US-001, US-008 |
| u2 briefing | ✅ Complete | 178 | US-002, US-009 |
| u3 publisher | ✅ Complete | 70 | US-003 (write half), US-006 |
| u4 notifier | ✅ Complete | 56 | US-004, US-007 |
| u5 orchestrator | ✅ Complete | 149 | US-005 (run half) |
| u6 infra/CI | ✅ Complete (this) | +15 (override side-quest) | US-005 (cron half), US-003 (Pages half) |
| **Total** | **All 6 ✅** | **720** | **All 9 user stories closed** |

---

## Pre-flight notes for global Build & Test

The next + final stage is global `Build and Test` (per `aidlc-workflows/aidlc-rules/aws-aidlc-rule-details/construction/build-and-test.md`). It's **the last construction milestone** for the project.

### What Build & Test will verify (per the AIDLC rule)

- **Build instructions** — repeatable from a clean checkout. For Investo:
  1. `uv python install 3.11`
  2. `uv sync --extra dev` (or `--extra dev --extra docs` for site preview)
  3. ready to run.
- **Unit test instructions** — `uv run pytest`. Currently **720/720** passing with 0 regressions across 6 units' worth of tests.
- **Integration test instructions** — already shipped: `tests/integration/test_pipeline.py` (u5; 7 tests; all 4 mock patterns wired), `tests/integration/test_briefing_pipeline_poc.py` (u2 cross-unit), `tests/integration/test_publisher_smoke.py` (u3), `tests/integration/test_notifier_smoke.py` (u4).
- **Site build instructions** — `uv run mkdocs build --strict` → `site/` populated. Cross-platform note: requires symlink support (see DEBT-027).

### What's NOT covered by automated test (operational verification only)

- **First production cron fire** — only verifiable in production. The runbook in CONTRIBUTING.md walks through it.
- **GitHub Pages first deploy** — same; the workflow is exercised by `mkdocs build --strict` locally + on the first push.
- **Telegram delivery** — exercised by integration smoke tests via httpx.MockTransport, but the actual bot/channel handshake only validates after the operator wires the secrets.

### Stable surface for Build & Test consumers

| Symbol | Defined in | Used by |
|--------|------------|---------|
| `python -m investo` | `__main__.main()` | `daily-briefing.yml` (production cron) |
| `uv run mkdocs build --strict` | `mkdocs.yml` | `pages.yml` (production deploy) |
| 5 GitHub Secrets contract | `__main__._REQUIRED_ENV_VARS` | Operator setup (per CONTRIBUTING.md runbook) |

### Failure paths the operator sees in production

(Already documented in u5's summary; reproduced here for u6's runbook context.)

| Failure | Where surfaced | Latency |
|---------|----------------|---------|
| Single source down | u1 swallows; pipeline still runs → SUCCESS | None (graceful) |
| Empty collect (all sources down or US holiday) | OperatorAlerter (Telegram 1:1) + GHA failure email | ≤ 1 min |
| LLM failure (Claude CLI down 3× in a row) | OperatorAlerter + GHA failure | ≤ 4 min |
| Disclaimer missing (NFR-004 hard block) | OperatorAlerter + GHA failure | ≤ 4 min |
| Git push failed 3× | OperatorAlerter + GHA failure | ≤ 5 min |
| Public-channel notify failed | PARTIAL (no operator alert; GHA shows green); operator checks the channel manually | None — visibility-only |
| Boot config error (missing secret etc.) | Best-effort OperatorAlerter (when token+operator-id present) + GHA email | ≤ 10 sec |
| `mkdocs build --strict` failure | GHA `pages` workflow red; previous site preserved (atomic deploy) | ≤ 1 min |

---

## Quality gate (final, Step 7 closeout)

| Tool | Result |
|------|--------|
| `ruff check .` | ✅ |
| `ruff format --check .` | ✅ (106 files) |
| `mypy --strict src/` | ✅ (37 source files) |
| `pytest` | ✅ **720/720** passing |
| `uv run mkdocs build --strict` | ✅ ("Documentation built in 0.30 seconds", zero warnings) |

---

## Next stage gate

`u6 infra/CI` Code Generation is now CLOSED. The unit becomes eligible for `/cross-check` against requirements. **All 6 units are now closed.** US-005 + US-003 close. **All 9 user stories are now closed.**

The only remaining stage is **global Build and Test**, which produces:
- `aidlc-docs/construction/build-and-test/build-instructions.md`
- `aidlc-docs/construction/build-and-test/unit-test-instructions.md`
- `aidlc-docs/construction/build-and-test/integration-test-instructions.md`
- `aidlc-docs/construction/build-and-test/build-and-test-summary.md`

…and runs the full quality gate against the integrated codebase one final time.
