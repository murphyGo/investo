# Code Generation Plan: `u6 infra/CI`

**Date**: 2026-04-30
**Unit**: u6 infra/CI — GitHub Actions + MkDocs + GitHub Pages
**Stage**: Code Generation (FD = N/A; NFR Requirements = N/A per execution-plan; YAML/config only — no new Python source code)

**Plan source**:
- `aidlc-docs/inception/application-design/unit-of-work.md` — u6 paths + DoD
- `docs/requirements.md` — FR-005 (cron schedule), FR-003 (mkdocs site), NFR-001 (≤10 min wall-clock), NFR-007 (Secrets)
- `aidlc-docs/construction/u5-orchestrator/code/summary.md` — Pre-flight notes for u6 (the stable `python -m investo` surface u6 wraps)
- `aidlc-docs/construction/u5-orchestrator/nfr-requirements/nfr-requirements.md` — AC-001-4 (`timeout-minutes: 12`), AC-007-1 (5 GitHub Secret names)
- `CLAUDE.md` — project rule #5 (chat ID disjointness — surfaces here as 2 separate Secrets)

---

## Unit Context

### Stories closed by this stage
- **US-005** (스케줄 실행) — closed alongside u5; u6 wires the GHA cron that triggers `python -m investo`. U5's `__main__` is the entrypoint; u6 is the trigger + secret plumbing.
- **US-003** (정적 게시) — partially closed by u3 (write_briefing + git push); u6 closes the public-site half (mkdocs build + Pages deploy).

### Dependencies
- **u5**: `python -m investo` is the entrypoint the cron workflow invokes. Must exit 0 on SUCCESS|PARTIAL, exit 1 on FAILED (per `__main__.py` mapping).
- **u3**: `archive/YYYY/MM/YYYY-MM-DD.md` is the directory layout mkdocs renders.
- **NEW external deps**: NONE for the runtime; `mkdocs-material` added to a dev/docs extra (not the runtime install).

### Definition of Done (from unit-of-work.md)
- [ ] cron 평일 KST 07:00 (UTC 22:00 전일) + 토 KST 09:00 (UTC 토 00:00) 실행
- [ ] `python -m investo`가 GitHub Secrets로 인증되어 동작
- [ ] commit 후 자동으로 Pages 빌드/배포
- [ ] 빌드 실패 시 기존 사이트 유지

### Module-boundary recap
**No Python source code in u6.** Files added:
- `.github/workflows/daily-briefing.yml`
- `.github/workflows/pages.yml`
- `mkdocs.yml`
- `docs/index.md` (mkdocs landing — must NOT collide with the existing `docs/` AIDLC documentation; resolution: keep AIDLC docs at `docs/` but configure mkdocs to read from a separate `site_docs/` dir, OR use `docs_dir: site_docs/` in mkdocs.yml. **Step 4 chooses the path during impl** — most likely option (b) since AIDLC docs are extensive and shouldn't render to public Pages.)
- `pyproject.toml` (extended) — add `[project.optional-dependencies] docs = ["mkdocs-material>=9.5"]` so contributors `pip install -e .[docs]` to build locally; CI installs `.[docs]` for the Pages job.

### Critical project rules (must hold in YAML)
1. **NFR-002 zero-cost**: GHA free tier; mkdocs-material is free; Pages is free.
2. **NFR-007 Secrets handling**: 5 secrets injected as `env:` block; never echoed to logs (GHA auto-masks `secrets.*` in step output).
3. **NFR-001 ≤10 min wall-clock**: `timeout-minutes: 12` per AC-001-4 (10-min design budget + 2-min margin).
4. **CLAUDE.md #5**: 2 separate Telegram secrets (`TELEGRAM_BRIEFING_CHANNEL_ID` ≠ `TELEGRAM_OPERATOR_CHAT_ID`); both injected to `env:` so u5's `_validate_env` can compare.
5. **FR-006 same-day re-run**: cron + manual `workflow_dispatch` both trigger the same job. Re-running on the same date overwrites the existing markdown (atomic write); git history retains versions.

---

## Steps

### Step 1: Project bootstrap

- [x] **1.1** Created `.github/workflows/` directory (was absent) + `site_docs/` directory (mkdocs source root, kept disjoint from existing `docs/` AIDLC docs).
- [x] **1.2** Added `[project.optional-dependencies] docs = ["mkdocs-material>=9.5"]` to `pyproject.toml`. Inline comment ratifies the rationale: dev/docs separation keeps the runtime install free of mkdocs/jinja/markdown machinery (NFR-002 minimal-runtime). Pin floor 9.5 chosen for Korean-friendly default search tokenization. Verified `uv sync --extra dev --extra docs` resolves; `uv run mkdocs --version` returns 1.6.1.
- [x] **1.3** Pre-created `site_docs/index.md` and `site_docs/about.md` placeholder pages — Step 4 fills them with real content. Path choice ratified: `site_docs/` (NOT `docs/`) so AIDLC documentation at `docs/` stays out of the public Pages render.
- [x] **1.4** Quality gate: ruff ✅, ruff format ✅ (106 files), mypy --strict ✅ (**37 source files** unchanged), pytest ✅ **705/705** unchanged. u6 doesn't add Python source or tests; the gate passes by being unchanged. Note: `uv sync --extra docs` alone replaces dev deps with docs deps; CI must use `uv sync --extra dev --extra docs` (or equivalent) to keep both. Documented in Step 5's CONTRIBUTING.md update.

---

### Step 2: `daily-briefing.yml` — cron + workflow_dispatch + `python -m investo`

**Refs**: FR-005 (cron schedule), AC-001-4 (`timeout-minutes: 12`), AC-007-1 (5 Secrets), US-005.

- [ ] **2.1** Create `.github/workflows/daily-briefing.yml`:
  - **Triggers**:
    - `schedule:` two cron entries:
      - `'0 22 * * 0,1,2,3,4'` — UTC Sun-Thu 22:00 = KST Mon-Fri 07:00 (5 entries; KST 평일 morning fires for prior-trading-day session).
      - `'0 0 * * 6'` — UTC Sat 00:00 = KST Sat 09:00 (one entry; Saturday morning fires for Friday's session).
    - `workflow_dispatch:` for manual trigger; allow optional `target_date` input (orchestrator's `target_date` parameter — useful for backfills + holiday-skip recoveries per Q3=A).
  - **Job `daily-briefing`**:
    - `runs-on: ubuntu-latest`
    - `timeout-minutes: 12` (AC-001-4)
    - `permissions: contents: write` (for `git push` from inside the runner)
    - **Steps**:
      1. `actions/checkout@v4` — full repo, fetch-depth=0 so `git push` lineage is clean.
      2. `astral-sh/setup-uv@v3` — install uv (the project's package manager per `uv.lock`).
      3. `uv python install 3.11` + `uv sync` — install Python 3.11 + project dependencies.
      4. Configure git author for the bot commit (`Investo Bot <bot@example.com>`).
      5. `uv run python -m investo` — the orchestrator entrypoint. `env:` block injects the 5 GitHub Secrets (`CLAUDE_CODE_OAUTH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BRIEFING_CHANNEL_ID`, `TELEGRAM_OPERATOR_CHAT_ID`, `SITE_URL_BASE`). Continues on success or PARTIAL (exit 0); fails the workflow on FAILED (exit 1).
- [ ] **2.2** Document the workflow in a comment header (cron schedule explanation w/ KST↔UTC conversion + DST note: KST has no DST since 1988; the cron times are stable year-round; US DST means the prior-trading-day's market close shifts ±1 hour twice a year but the cron fires at the same KST clock time).
- [ ] **2.3** Verification: render the workflow file with `gh workflow list` (after push). The workflow file is YAML-validated at GHA's parse time; we can also run `actionlint` locally if installed.

---

### Step 3: `pages.yml` — mkdocs build + actions/deploy-pages

**Refs**: FR-003 (정적 사이트), US-003.

- [ ] **3.1** Create `.github/workflows/pages.yml`:
  - **Triggers**:
    - `push:` on `main` (so any commit — including the daily-briefing job's `git push` — triggers a rebuild).
    - `workflow_dispatch:` for manual rebuild.
  - **Job `build`**:
    - `runs-on: ubuntu-latest`
    - `permissions: { pages: write, id-token: write, contents: read }` (the `actions/deploy-pages@v4` standard set).
    - **Steps**:
      1. `actions/checkout@v4`.
      2. uv setup (same pattern as Step 2).
      3. `uv sync --extra docs` — install mkdocs-material.
      4. `uv run mkdocs build --strict` — build into `site/`. `--strict` fails on broken links / unrecognized config (FR-006 quality gate).
      5. `actions/configure-pages@v5` + `actions/upload-pages-artifact@v3 with: path: site` + `actions/deploy-pages@v4`.
  - **DoD: "빌드 실패 시 기존 사이트 유지"**: implicit via GHA's deploy-pages atomic swap. If `mkdocs build` fails or upload fails, the previously-deployed site remains at `gh-pages` until the next successful run.
- [ ] **3.2** Verification: `uv run mkdocs build --strict` locally produces `site/` without errors before relying on CI.

---

### Step 4: `mkdocs.yml` + landing pages

**Refs**: FR-003, US-003.

- [ ] **4.1** Create `mkdocs.yml`:
  - `site_name: Investo — 데일리 시황`
  - `site_url: https://{operator-username}.github.io/investo/` (placeholder; final value set via `SITE_URL_BASE` env var conventionally not in the YAML).
  - `docs_dir: site_docs/` — read from a separate dir to avoid colliding with AIDLC docs at `docs/`. **Decision**: pick option (b) from Step Context — pull mkdocs source from `site_docs/` so `docs/` keeps AIDLC documentation untouched.
  - `theme:` mkdocs-material with Korean-friendly defaults.
  - `nav:` minimal — Home / About / Archive (auto-generated from `archive/`).
  - `plugins:` reading the `archive/YYYY/MM/YYYY-MM-DD.md` directory tree. Use mkdocs-material's `awesome-pages` or stick with stdlib `nav` glob — **Step 4 picks during impl**; minimum viable is to point `archive/` as a tracked subdirectory.
- [ ] **4.2** Create `site_docs/index.md` — landing page. Brief description (Korean) of the project + link to latest briefing.
- [ ] **4.3** Create `site_docs/about.md` — operator info, project source link, "투자 자문이 아닙니다" disclaimer at the bottom.
- [ ] **4.4** Configure mkdocs to surface the `archive/YYYY/MM/YYYY-MM-DD.md` tree as a navigable section. Two options:
  - **(a) symlink `archive/` into `site_docs/archive/`** — simpler but adds a runtime symlink to manage.
  - **(b) configure `docs_dir` to include both `site_docs/` and `archive/`** via plugin or post-process.
  - **Plan recommendation: option (a)** — minimal moving parts; the symlink is created once + tracked by git as a special file.

---

### Step 5: `pyproject.toml` extension + `CONTRIBUTING.md` update

**Refs**: NFR-002 (zero new runtime deps; mkdocs is dev-only).

- [ ] **5.1** Edit `pyproject.toml`:
  - Add `[project.optional-dependencies] docs = ["mkdocs-material>=9.5"]`.
  - Verify the existing `[project] dependencies` list doesn't include any of the TS-10 deny-list packages (regression check; should be unchanged from u5).
- [ ] **5.2** Edit `CONTRIBUTING.md` (or create if absent):
  - Document the GHA cron schedule (2 cron entries + KST→UTC conversion).
  - Document the 5 required Secrets (names + provenance).
  - Document the manual `workflow_dispatch` trigger (target_date input).
  - Document `uv run mkdocs build --strict` for local site preview.
  - Document the operator's manual-recovery flow for US public holidays (Q3=A): re-run with `workflow_dispatch + target_date=last-trading-day`.

---

### Step 6: Sub-agent code review

Delegate fresh-eyes review per dev-investo §5.1. Focus areas:
- **YAML syntax**: workflow files parse cleanly (mental run + actionlint if available).
- **Secret handling**: 5 secrets injected via `env:` block; not echoed; not logged by accident.
- **Cron interpretation**: KST↔UTC cron conversion is correct + accounts for KST having no DST.
- **`timeout-minutes: 12`**: matches AC-001-4.
- **Permissions principle of least privilege**: daily-briefing has `contents: write` only; pages has `pages: write, id-token: write, contents: read` only.
- **Deploy atomicity**: `actions/deploy-pages@v4` provides this; verify the DoD "빌드 실패 시 기존 사이트 유지".
- **Module boundary** (CLAUDE.md #3): u6 is YAML/config; doesn't import any Python module from sources/briefing/publisher/notifier/orchestrator.
- **Zero-cost (NFR-002)**: GHA free tier + Pages free + mkdocs-material is free open-source.

After review: apply Critical / High fixes; triage Medium / Low into TECH-DEBT or apply.

---

### Step 7: Closeout `summary.md` + final quality gate

- [ ] **7.1** Create `aidlc-docs/construction/u6-infra-ci/code/summary.md`:
  - Files-created table (4 YAML + 2 markdown + pyproject extension + CONTRIBUTING update).
  - DoD verification table (4 DoD items × evidence).
  - Story status: US-005 ✅ closed (cron half), US-003 ✅ closed (Pages half).
  - Open TECH-DEBT (none expected from u6 itself; carry forward 21 from prior).
  - Hand-off notes for global Build & Test (the next + final stage).
- [ ] **7.2** Final quality gate: ruff ✅ (Python unchanged), ruff format ✅, mypy --strict ✅ (37 source files unchanged), pytest ✅ (705/705 unchanged), `uv run mkdocs build --strict` ✅ locally.

**Exit**: ✅ `u6 infra/CI` Code Generation stage CLOSED. Stories US-005 + US-003 fully close. **All 6 units complete.** Next: global `Build and Test` stage (the project's final construction milestone).

---

## Step Dependency Graph

```
1 bootstrap
  └── 2 daily-briefing.yml         (depends on u5's __main__)
  └── 3 pages.yml                  (depends on 4 mkdocs.yml)
  └── 4 mkdocs.yml + landing       (creates site structure)
        └── 5 pyproject + CONTRIBUTING  (declares mkdocs-material)
              └── 6 sub-agent review
                    └── 7 closeout
```

In practice: 1 → 2 || (4 → 3) → 5 → 6 → 7 (Steps 2 and 4 are independent; commit them in either order).

---

## Estimated Scope

- ~4 YAML files (`.github/workflows/daily-briefing.yml`, `.github/workflows/pages.yml`, `mkdocs.yml`, possibly `actionlint.yml`)
- ~2 markdown source pages (`site_docs/index.md`, `site_docs/about.md`)
- pyproject.toml extension (1 optional-dep)
- CONTRIBUTING.md update (operator runbook)
- 0 new Python source code; 0 new Python tests
- ~7 plan steps, each yielding 1 commit
- Solo dev: ~half a day (smaller than other units; pure config)

---

## How to Approve

This plan is the single source of truth for `u6` Code Generation. Reply
**approve** to begin Step 1; **changes [N]** to revise step N.
