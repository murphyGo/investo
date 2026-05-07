# Cross-Check: u27 secret-hygiene-unification-and-cost-guard

**Scope**: u27 secret-hygiene-unification-and-cost-guard
**Date**: 2026-05-08
**Checked by**: Codex

---

## Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Complete | 6 | 100% |
| ⚠️ Partial | 0 | 0% |
| ❌ Gap | 0 | 0% |
| 🔄 Deferred | 0 | 0% |
| ⏳ In Progress | 0 | 0% |
| **Total** | **6** | **100%** |

**Overall Compliance**: 100%

---

## Scope Mapping

u27 is a Wave 1 P0 follow-up from the 2026-05-07 persona evaluation (persona #5) that consolidates four previously divergent secret-redaction sites into a single chokepoint and adds a code-level cost guard for the OpenAI visual surface so the "0원 운영비" KPI is enforced at runtime rather than by convention. The unit does not introduce paid sources, accounts, trading, or new external dependencies.

**Plan**: `aidlc-docs/construction/plans/u27-secret-hygiene-unification-and-cost-guard-code-generation-plan.md`
**Goal**: Unify the four divergent sanitize policies (coverage / provenance / leak-guard / `__main__` diagnostics) into one chokepoint, and integrate the OpenAI visual surface with redaction / preflight / workflow gating so the "0원 운영비" KPI is enforced at the code level rather than by convention.

| Requirement Area | Status | Evidence | Notes |
|------------------|--------|----------|-------|
| FR-001 source aggregation diagnostics | ✅ | `src/investo/models/coverage.py`, `tests/unit/_internal/test_redaction.py` | `sanitize_source_error_message` now delegates to `redact_text(..., policy=RedactionPolicy.STRICT)`; per-source error rendering keeps R8/R13 hygiene without a duplicate regex set. |
| FR-002 Korean briefing comprehension | ✅ | `src/investo/visuals/provenance.py`, `src/investo/briefing/leak_guard.py`, `tests/unit/_internal/test_redaction.py` | Provenance captions and leak-guard scans now share the same redaction patterns (STRICT vs URL_AWARE) so reader-facing strings cannot drift across surfaces. |
| FR-003 static web publishing | ✅ | `src/investo/visuals/provenance.py`, `src/investo/_internal/redaction.py` | Visual sidecars and SVG captions inherit the chokepoint by construction; no new external HTTP introduced. |
| FR-008 segmented briefing | ✅ | `src/investo/briefing/leak_guard.py`, `src/investo/_internal/redaction.py` | Per-segment leak-guard scans use `URL_AWARE` precedence so segment markdown excerpt false-positives stay bounded while the canonical secret shapes still redact. |
| NFR-002 cost / no paid APIs | ✅ | `.github/workflows/daily-briefing.yml`, `scripts/check_daily_briefing_env.py`, `src/investo/__main__.py` (`_validate_env`) | Triple fail-safe: workflow forces `INVESTO_OPENAI_VISUALS=0` on both daily-briefing entry points, preflight script branches on the opt-in flag, and `_validate_env` rejects any runtime path that flips the flag without `OPENAI_API_KEY`. No paid call can be issued from CI. |
| NFR-003 graceful degradation | ✅ | `src/investo/__main__.py`, `src/investo/_internal/redaction.py` | Missing-secret diagnostic strings flow through `redact_text` so degradation messages cannot leak partial values; existing PARTIAL/FAIL paths unchanged. |
| NFR-004 compliance / disclaimer boundary | ✅ | `src/investo/orchestrator/pipeline.py` (unchanged), `src/investo/_internal/redaction.py` | Disclaimer enforcement is unchanged; redaction operates upstream of `verify_disclaimer`. |
| NFR-005 consistency / DRY | ✅ | `src/investo/_internal/redaction.py`, `tests/unit/_internal/test_redaction.py::TestSurfacesShareChokepoint` | All five surfaces (`__main__`, `coverage`, `provenance`, `leak_guard`, `_telegram`) share one regex tuple plus one env-var tuple; parametrize anti-regression test pins it. |
| NFR-006 testing | ✅ | `tests/unit/_internal/test_redaction.py`, full quality gate | +71 targeted tests (1076 → 1147); chokepoint, parametrized surface coverage, env-var coverage, and STRICT vs URL_AWARE precedence all pinned. |
| NFR-007 secret hygiene (R8 / R13) | ✅ | `src/investo/_internal/redaction.py`, `src/investo/notifier/_telegram.py` (M1) | Single chokepoint covers bot-token / chat-id / FRED / OpenAI / generic high-entropy shapes; `_telegram._redact_bot_token` is now a thin shim above the chokepoint with marker `[REDACTED_BOT_TOKEN]`. |

---

## Definition of Done

| Criterion | Status | Evidence |
|-----------|--------|----------|
| A new shared module (`src/investo/_internal/redaction.py`) exposes a single `redact_text` chokepoint used by `__main__._redact_diagnostic_text`, `models.coverage.sanitize_source_error_message`, `visuals.provenance.sanitize_provenance_text`, and `briefing.leak_guard`. | ✅ | `src/investo/_internal/redaction.py` (new), `src/investo/__main__.py`, `src/investo/models/coverage.py`, `src/investo/visuals/provenance.py`, `src/investo/briefing/leak_guard.py`, `src/investo/notifier/_telegram.py` (M1 shim) — 5 surfaces total, all routing through the chokepoint. |
| DEBT-035 / DEBT-036 / DEBT-042 are resolved by the chokepoint and moved under TECH-DEBT Resolved Items. | ✅ | `docs/TECH-DEBT.md` Resolved section: DEBT-035 (regex duplication), DEBT-036 (`_SECRET_ENV_VARS` width mismatch), DEBT-042 (sanitizer policy unification). |
| `_REQUIRED_ENV_VARS` (or equivalent preflight) lists `OPENAI_API_KEY` and treats it as a redaction target. | ✅ | `src/investo/__main__.py::_validate_env` (opt-in branch), `src/investo/_internal/redaction.py::SECRET_ENV_VARS` (includes `OPENAI_API_KEY`), `scripts/check_daily_briefing_env.py` (opt-in branch). |
| GitHub Actions workflow forces `INVESTO_OPENAI_VISUALS=0` (or fails closed when the secret is absent) so OpenAI visuals stay off by default. | ✅ | `.github/workflows/daily-briefing.yml` — both daily-briefing job steps set `INVESTO_OPENAI_VISUALS: '0'` and inject `OPENAI_API_KEY` for future opt-in only; preflight + `_validate_env` form the second and third fail-safes. |
| `.github/dependabot.yml` adds a `package-ecosystem: pip` group covering project dependencies. | ✅ | `.github/dependabot.yml` — `pip` ecosystem entry added under the existing weekly schedule. |
| CONTRIBUTING runbook section explicitly documents the OpenAI-disabled default and the override contract. | ✅ | `CONTRIBUTING.md` runbook section — OpenAI default-off, opt-in flag, and 3중 fail-safe contract documented. |

---

## Verification

- `uv run ruff check .` — passed
- `uv run ruff format --check .` — passed (172 files)
- `uv run mypy --strict src/` — passed (66 source files)
- `uv run pytest -q` — 1147 passed (1076 → 1147, +71 new tests)
- `uv run mkdocs build --strict` — to be re-verified at the close of the u25-u33 follow-up wave (no new mkdocs nav/content changes in u27)

---

## Project Rule Compliance

| Rule | Status | Notes |
|------|--------|-------|
| Anthropic SDK import 금지 (CLI only) | ✅ | u27 does not introduce any LLM client; the OpenAI integration is contract-only and gated off by default. No Anthropic SDK import added. |
| 모듈 경계 (only orchestrator imports the four units) | ✅ | The new `src/investo/_internal/redaction.py` is stdlib-only (`re`, `typing`) — no cross-unit imports; each consuming surface (`__main__`, `models.coverage`, `visuals.provenance`, `briefing.leak_guard`, `notifier._telegram`) imports the helper directly without crossing unit-to-unit boundaries. |
| 무료 API only | ✅ | Triple fail-safe enforces the OpenAI visual path stays off: workflow forces `INVESTO_OPENAI_VISUALS=0`, preflight branches on the opt-in flag, `_validate_env` rejects any runtime path lacking `OPENAI_API_KEY` when the flag is on. No paid call reachable from CI today. |
| 면책조항 자동 삽입 | ✅ | Publisher's `verify_disclaimer` remains the publish-time gate; redaction operates upstream and does not touch the disclaimer surface. |
| 텔레그램 채널 분리 (public ≠ operator) | ✅ | u27 does not change notifier targets; existing public/operator separation is preserved. M1 fix only refactors `_telegram._redact_bot_token` into a chokepoint shim with marker `[REDACTED_BOT_TOKEN]`. |
| R8 (raw_metadata / source provenance) | ✅ | All user-/operator-derived strings continue to flow through `sanitize_source_error_message` / `sanitize_provenance_text`, both now delegating to the single chokepoint. |
| R13 (no secret values in logs / errors / raw_metadata / fixtures) | ✅ | Single chokepoint covers bot-token / chat-id / FRED / OpenAI / generic high-entropy shapes. `tests/unit/_internal/test_redaction.py::TestSurfacesShareChokepoint` parametrizes all 5 surfaces against every canonical secret shape. |
| `defusedxml` only (no raw stdlib XML) | ✅ | u27 does not introduce any new XML parsing path; existing `defusedxml`-based source adapters remain unchanged. |

---

## QA Verdict

- Verdict: **APPROVE_AFTER_FIXES**
- Pre-merge fixes applied:
  - **M1** — `notifier/_telegram._redact_bot_token` rewritten as a thin shim above the `redact_text` chokepoint, with marker `[REDACTED_BOT_TOKEN]` preserved for backwards-compatible operator alert formatting. Brings the 5th surface (telegram error rendering) onto the single chokepoint.
  - **M2** — Added a parametrize anti-regression test (`tests/unit/_internal/test_redaction.py::TestSurfacesShareChokepoint`) that cross-tests all 5 surfaces (`__main__._redact_diagnostic_text`, `models.coverage.sanitize_source_error_message`, `visuals.provenance.sanitize_provenance_text`, `briefing.leak_guard.scan`, `notifier._telegram._redact_bot_token`) against every canonical secret shape. A future surface drift fails the matrix.
- Deferred to TECH-DEBT:
  - **M3** → DEBT-044 (Low) — `_QUERY_REDACT_RE` over-redacts in URL_AWARE callers; latent today (no URL_AWARE caller of `redact_text` exists), surfaces if a future markdown-excerpt caller adopts URL_AWARE.
  - **M4** → DEBT-045 (Low) — `_LONG_BASE64_RE` does not include URL-safe base64 (`-`, `_`); Slack `xoxb-...` and URL-safe GitHub fine-grained PAT shapes can slip the generic catch-all.
- No Critical or High findings.

---

## TECH-DEBT Surfaced by This Unit

Two new low-priority items registered (`docs/TECH-DEBT.md`):

- **DEBT-044 (Low)** — `_QUERY_REDACT_RE` over-redacts in URL_AWARE callers. Currently latent because the only URL_AWARE caller is `scan_for_leak`, not `redact_text`. Fix: apply query-redact only under STRICT, or document the caveat in the URL_AWARE docstring.
- **DEBT-045 (Low)** — `_LONG_BASE64_RE` does not include URL-safe base64 characters (`-`, `_`); URL-safe oauth tokens (Slack `xoxb-...`, some GitHub fine-grained PAT shapes) can slip the generic catch-all even though the JWT/GitHub PAT specific patterns cover most cases. Fix: extend to `[A-Za-z0-9+/_-]{40,}={0,2}` and recalibrate URL_AWARE false-positive surface.

Three previously open items are resolved by this unit:

- **DEBT-035 (Low)** — Bot-token / chat-id redaction regex duplicated across `__main__` and `models/coverage`. Resolved 2026-05-08.
- **DEBT-036 (Low)** — `_SECRET_ENV_VARS` width mismatch between `__main__` and `models/coverage`. Resolved 2026-05-08.
- **DEBT-042 (Medium)** — Sanitizer policy unification across coverage / provenance / leak-guard. Resolved 2026-05-08.

---

## Gaps Analysis

No gaps found.

## Proposed Actions

- No requirements/design changes.
- TECH-DEBT updates already registered (DEBT-044, DEBT-045 added; DEBT-035 / DEBT-036 / DEBT-042 resolved).
- `mkdocs build --strict` to be re-verified once the broader u25-u33 follow-up wave closes.
