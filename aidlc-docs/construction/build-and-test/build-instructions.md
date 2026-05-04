# Build Instructions

**Project**: Investo — Daily market briefing automation
**Build tool**: `uv` (the project's package manager; `uv.lock` is the lockfile)
**Date**: 2026-05-04

---

## Prerequisites

- **OS**: Linux or macOS (tested on Ubuntu 24.04 / macOS 14.5+).
  - Windows is not a v1 target. The `site_docs/archive` symlink requires `core.symlinks=true` plus Windows Developer Mode/admin privileges if a Windows checkout is ever needed; this is documented in `CONTRIBUTING.md`.
- **Python**: 3.11 (per `pyproject.toml requires-python = ">=3.11"`; CI pins 3.11 via `uv python install 3.11`).
- **`uv`**: ≥ 0.4 (any version with `uv sync --extra ...` support; CI uses a SHA-pinned `astral-sh/setup-uv` action).
- **`claude` CLI**: required only for live runs of `python -m investo`. Not needed for `pytest` or `mkdocs build` because all tests use either record/replay fixtures (`FakeClaudeRunner` for u2 → CI) or mocked `MockTransport` for HTTP calls.
- **`git`**: required because `commit_and_push` (u3) shells out to `git`. Tests use a fake `GitRunner` Protocol implementation; production CI uses the real binary.
- **System resources**: < 1 GB RAM during tests; < 100 MB disk for the venv + dependencies.

## Required environment variables (production only)

The 5 secrets required by `python -m investo`:

| Variable | Source | Purpose |
|----------|--------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | `claude /login` setup token | LLM authentication (NFR-002 / US-009 — no Anthropic SDK) |
| `TELEGRAM_BOT_TOKEN` | BotFather `/newbot` | Telegram bot identity |
| `TELEGRAM_BRIEFING_CHANNEL_ID` | `@your_public_channel` or numeric ID | Public briefing channel (FR-004) |
| `TELEGRAM_OPERATOR_CHAT_ID` | Operator's 1:1 chat ID | Operator failure alerts (FR-007); MUST be disjoint from CHANNEL_ID |
| `SITE_URL_BASE` | e.g. `https://murphygo.github.io/investo` | Base URL for per-day briefing footer |

**These are NOT needed for the build or test phases — only for `python -m investo` live runs.** All test paths use injected fakes.

---

## Build steps

### 1. Install dependencies

```bash
# Production runtime + tests
uv sync --extra dev

# OR for site builds (mkdocs):
uv sync --extra docs

# OR both (local dev):
uv sync --extra dev --extra docs
```

**Important**: `uv sync --extra docs` ALONE replaces dev deps (default uv behavior). For combined work, list both extras explicitly.

**Runtime deps locked** (`pyproject.toml [project] dependencies`):
- `pydantic>=2.0` (validation + serialization)
- `httpx>=0.27` (async HTTP for u1 / u4)
- `defusedxml>=0.7` (XML parsing safety in u1 source adapters)
- `bleach>=6` (HTML sanitization in u1)

**Dev extras**: `pytest>=8`, `pytest-asyncio>=0.23`, `hypothesis>=6`, `ruff>=0.5`, `mypy>=1.8`, `types-bleach`, `types-defusedxml`.

**Docs extras**: `mkdocs-material>=9.5` (Korean tokenization).

### 2. Configure environment

For the build / test phase, no environment configuration is required. For the operational phase (`python -m investo`), see the GitHub Secrets table above.

### 3. Build the package (optional — only if installing)

```bash
# Build wheel + sdist into ./dist/
uv build
```

The package builds via `hatchling` (declared in `pyproject.toml [build-system]`); no compilation step is required (pure Python).

For local development, an editable install is automatic via `uv sync` (no `pip install -e .` needed; uv handles it).

### 4. Verify build success

The "build" for Investo is essentially the dependency lockfile resolution + import verification:

```bash
# Sanity import check
uv run python -c "import investo; print('OK')"
```

Expected output: `OK`.

---

## Build artifacts

| Artifact | Location | Produced by |
|----------|----------|-------------|
| Locked venv | `.venv/` | `uv sync` |
| `archive/YYYY/MM/YYYY-MM-DD.md` | `archive/` | `python -m investo` (production) |
| Public site | `site/` | `uv run mkdocs build --strict` |
| Python wheel | `dist/*.whl` | `uv build` (optional) |

`.venv/`, `site/`, `dist/` are gitignored (`.gitignore`). `archive/` is tracked (briefings are the project's deliverable).

---

## Troubleshooting

### `uv sync` fails with dependency resolution error

**Cause**: `uv.lock` may be stale relative to `pyproject.toml` (rare; happens after a manual edit of `pyproject.toml [project] dependencies` without re-running `uv lock`).

**Solution**:
```bash
uv lock --refresh
uv sync --extra dev
```

### `uv run python -m investo` exits 1 with `ConfigError`

**Cause**: One or more of the 5 GitHub Secrets is missing (or set to an empty string).

**Solution**: see the operator runbook in `CONTRIBUTING.md` (the "GitHub Secrets" table identifies each missing var).

### `uv run mkdocs build --strict` fails with `[archive/index.md] file is not in docs directory`

**Cause**: `site_docs/archive` symlink is missing from the working tree (rare — happens on a Windows checkout without `core.symlinks=true`, or if the symlink was accidentally `git rm`-ed).

**Solution**:
```bash
ln -s ../archive site_docs/archive
git add site_docs/archive
```

The symlink is mode 120000 in the git index. Verify with `git ls-files --stage site_docs/`.

### `uv run pytest` fails on a fresh checkout

**Cause**: A pre-existing test environment (`.pytest_cache/` or stale `.venv/`).

**Solution**:
```bash
rm -rf .venv .pytest_cache .mypy_cache .ruff_cache
uv sync --extra dev
uv run pytest
```

---

## Quality gate (every PR)

All four checks must pass before merge:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/
uv run pytest
```

If touching site config (`mkdocs.yml`, `site_docs/`, `pyproject.toml [project.optional-dependencies] docs`):

```bash
uv sync --extra dev --extra docs
uv run mkdocs build --strict
```

CI runs the same gate on every push (per `.github/workflows/`); local pre-commit verification ensures fast feedback.
