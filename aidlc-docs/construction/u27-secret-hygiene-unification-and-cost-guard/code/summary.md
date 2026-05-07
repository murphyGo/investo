# Code Summary: u27 secret-hygiene-unification-and-cost-guard

**Date**: 2026-05-08

## Completed

- Introduced `src/investo/_internal/redaction.py` as the single secret-redaction chokepoint. The module owns `SECRET_PATTERNS` (bot-token, chat-id, FRED key, OpenAI key, JWT, GitHub PAT, generic high-entropy), `SECRET_ENV_VARS` (6 names — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_PUBLIC_CHANNEL_ID`, `TELEGRAM_OPERATOR_CHAT_ID`, `FRED_API_KEY`, `OPENAI_API_KEY`, `INVESTO_GIT_TOKEN`), and a `RedactionPolicy` enum (`STRICT` for diagnostic / coverage / provenance / telegram surfaces, `URL_AWARE` for the leak-guard markdown-excerpt scan). Public entry points are `redact_text(...)` (returns the redacted string) and `scan_for_leak(...)` (returns a leak-shape iterator).
- Migrated five surfaces onto the chokepoint:
  - `src/investo/__main__.py::_redact_diagnostic_text` — STRICT.
  - `src/investo/models/coverage.py::sanitize_source_error_message` — STRICT (delegate; previously carried its own regex set).
  - `src/investo/visuals/provenance.py::sanitize_provenance_text` — STRICT (delegate; previously delegated to coverage's regex set).
  - `src/investo/briefing/leak_guard.py::scan` — URL_AWARE (uses `scan_for_leak` so URL query strings do not over-redact for markdown excerpt scans).
  - `src/investo/notifier/_telegram.py::_redact_bot_token` — STRICT shim (M1 fix). Marker `[REDACTED_BOT_TOKEN]` preserved for operator-alert formatting parity.
- Resolved DEBT-035 (regex duplication), DEBT-036 (`_SECRET_ENV_VARS` width mismatch), and DEBT-042 (sanitizer policy unification) by construction. New surfaces inherit the full pattern set the moment they pick `STRICT` or `URL_AWARE`.
- Wired the OpenAI cost guard as a triple fail-safe so the "0원 운영비" KPI is enforced at the code level rather than by convention:
  1. `.github/workflows/daily-briefing.yml` forces `INVESTO_OPENAI_VISUALS: '0'` on both daily-briefing job entry points and injects `OPENAI_API_KEY` only as a future opt-in slot.
  2. `scripts/check_daily_briefing_env.py` branches on the opt-in flag — when `INVESTO_OPENAI_VISUALS=1` and `OPENAI_API_KEY` is missing, preflight fails closed.
  3. `src/investo/__main__.py::_validate_env` rejects the runtime opt-in when `OPENAI_API_KEY` is absent, so even a manually set flag cannot reach the visual surface without the secret.
- Added `pip` ecosystem to `.github/dependabot.yml` so project Python dependencies stay current under the same weekly schedule as `github-actions`.
- Documented the OpenAI default-off contract and the override path in the `CONTRIBUTING.md` runbook section, including the 3중 fail-safe mental model.
- Applied M1 (`_telegram._redact_bot_token` chokepoint shim) and M2 (5-surface parametrize anti-regression test) pre-merge. M3 / M4 deferred to DEBT-044 / DEBT-045.

## Files Changed

### New source files

- `src/investo/_internal/__init__.py`
- `src/investo/_internal/redaction.py` (new — single chokepoint)

### Modified source files

- `src/investo/__main__.py` (delegate to chokepoint, opt-in OpenAI branch in `_validate_env`)
- `src/investo/models/coverage.py` (delegate `sanitize_source_error_message` to chokepoint)
- `src/investo/visuals/provenance.py` (delegate `sanitize_provenance_text` to chokepoint)
- `src/investo/briefing/leak_guard.py` (delegate scan to `scan_for_leak` URL_AWARE)
- `src/investo/notifier/_telegram.py` (M1 — `_redact_bot_token` chokepoint shim)

### New test files

- `tests/unit/_internal/__init__.py`
- `tests/unit/_internal/test_redaction.py` (new — chokepoint, parametrize 5-surface coverage, env-var coverage, STRICT vs URL_AWARE precedence)

### Modified infra / scripts

- `.github/workflows/daily-briefing.yml` (`INVESTO_OPENAI_VISUALS: '0'` on both daily-briefing entry points + `OPENAI_API_KEY` injection slot)
- `.github/dependabot.yml` (`pip` ecosystem group added)
- `scripts/check_daily_briefing_env.py` (opt-in OpenAI branch)
- `CONTRIBUTING.md` (runbook section — OpenAI default-off + 3중 fail-safe contract)

### Modified documentation

- `docs/TECH-DEBT.md` (DEBT-035 / DEBT-036 / DEBT-042 moved under Resolved Items; DEBT-044 / DEBT-045 added)
- `docs/cross-checks/2026-05-08-u27-secret-hygiene-unification-and-cost-guard.md` (new)
- `aidlc-docs/audit.md`
- `aidlc-docs/aidlc-state.md`
- `aidlc-docs/construction/plans/u27-secret-hygiene-unification-and-cost-guard-code-generation-plan.md` (DoD + step checkboxes marked)

## Linked Requirements / FRs / NFRs / ACs

- **FR-001** — coverage error rendering keeps R8/R13 hygiene through the shared chokepoint.
- **FR-002** — provenance captions and leak-guard scans share the same redaction patterns; reader-facing strings cannot drift across surfaces.
- **FR-003** — visual sidecars and SVG captions inherit the chokepoint by construction.
- **FR-008** — per-segment leak-guard scans use `URL_AWARE` precedence so segment markdown excerpt false-positives stay bounded.
- **NFR-002 (cost / no paid APIs)** — triple fail-safe (workflow + preflight + `_validate_env`) blocks any paid OpenAI call from CI today.
- **NFR-003 (graceful degradation)** — degradation diagnostics flow through `redact_text`; existing PARTIAL/FAIL paths unchanged.
- **NFR-004 (compliance / disclaimer)** — `verify_disclaimer` remains the publish-time gate; redaction is upstream.
- **NFR-005 (consistency / DRY)** — single regex tuple + single env-var tuple shared across 5 surfaces.
- **NFR-006 (testing)** — +71 targeted tests (1076 → 1147); chokepoint, parametrize 5-surface coverage, env-var coverage, STRICT vs URL_AWARE precedence pinned.
- **NFR-007 (R8 / R13)** — single chokepoint covers bot-token / chat-id / FRED / OpenAI / generic high-entropy shapes; `_telegram._redact_bot_token` is now a thin shim above the chokepoint with marker `[REDACTED_BOT_TOKEN]`.

## Architecture Summary

```
_internal/
  redaction.py          # NEW — single chokepoint
                        #   SECRET_PATTERNS:   tuple of (compiled regex, replacement) pairs
                        #   SECRET_ENV_VARS:   tuple of secret env-var names (6 entries)
                        #   RedactionPolicy:   enum {STRICT, URL_AWARE}
                        #   redact_text(...):  STRICT-or-URL_AWARE redaction pass
                        #   scan_for_leak(..): URL_AWARE leak-shape iterator
                        # stdlib-only: re, typing
                        # no cross-unit imports

  ┌──────────────────────────────────────────┐
  │             redact_text (STRICT)         │
  └──────────────────────────────────────────┘
       ▲          ▲          ▲          ▲
       │          │          │          │
   __main__   coverage   provenance   _telegram
   (diag)    (R8/R13)   (R8/R13)    (M1 shim)

  ┌──────────────────────────────────────────┐
  │           scan_for_leak (URL_AWARE)      │
  └──────────────────────────────────────────┘
       ▲
       │
   leak_guard
   (segment markdown excerpt)
```

The chokepoint is the only place the rest of the codebase constructs a redaction pass. Adding a sixth surface is a one-line `from investo._internal.redaction import redact_text` plus a policy choice; the parametrize anti-regression test (`TestSurfacesShareChokepoint`) automatically covers the new surface once it is added to the matrix.

The OpenAI cost guard is similarly chokepointed — one boolean flag (`INVESTO_OPENAI_VISUALS`) is the single switch; three independent fail-safes ensure that flipping it requires both an explicit operator action and a present secret:

```
GHA workflow ──► INVESTO_OPENAI_VISUALS=0  (forced on every CI run)
                          │
                          ▼
preflight script ──► fails closed when flag=1 ∧ OPENAI_API_KEY missing
                          │
                          ▼
_validate_env  ───► rejects runtime when flag=1 ∧ OPENAI_API_KEY missing
```

## QA Outcome

- Verdict: APPROVE_AFTER_FIXES.
- M1 (`_telegram._redact_bot_token` chokepoint shim) and M2 (5-surface parametrize anti-regression test) applied pre-merge.
- M3 deferred → DEBT-044 (Low) — `_QUERY_REDACT_RE` over-redacts in URL_AWARE callers; latent today.
- M4 deferred → DEBT-045 (Low) — `_LONG_BASE64_RE` missing URL-safe base64 characters.
- DEBT-035 / DEBT-036 / DEBT-042 resolved by construction; entries moved under TECH-DEBT Resolved Items.
- Cross-check: `docs/cross-checks/2026-05-08-u27-secret-hygiene-unification-and-cost-guard.md`.

## Verification

- `uv run ruff check .`
- `uv run ruff format --check .` (172 files)
- `uv run mypy --strict src/` (66 source files)
- `uv run pytest -q` (1147 passed; 1076 → 1147, +71 new tests)
- `uv run mkdocs build --strict` — to be re-verified at the close of the u25-u33 follow-up wave.
