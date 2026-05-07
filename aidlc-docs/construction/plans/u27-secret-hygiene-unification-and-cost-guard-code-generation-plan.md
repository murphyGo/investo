# Code Generation Plan: `u27 secret-hygiene-unification-and-cost-guard`

**Date**: 2026-05-08
**Unit**: u27 secret-hygiene-unification-and-cost-guard
**Stage**: Code Generation

---

## Goal

Unify the four divergent sanitize policies into one chokepoint and integrate the OpenAI visual surface with redaction / preflight / workflow gating so the "0원 운영비" KPI is enforced at the code level rather than by convention.

---

## Definition of Done

- [x] A new shared module (e.g. `src/investo/_internal/redaction.py`) exposes a single `redact_text` chokepoint used by `__main__._redact_diagnostic_text`, `models.coverage.sanitize_source_error_message`, `visuals.provenance.sanitize_provenance_text`, and `briefing.leak_guard`.
- [x] DEBT-035 (regex duplication), DEBT-036 (`_SECRET_ENV_VARS` width mismatch), and DEBT-042 (sanitizer policy unification) are resolved by the chokepoint and moved under TECH-DEBT Resolved Items.
- [x] `_REQUIRED_ENV_VARS` (or equivalent preflight) lists `OPENAI_API_KEY` and treats it as a redaction target.
- [x] GitHub Actions workflow forces `INVESTO_OPENAI_VISUALS=0` (or fails closed when the secret is absent) so OpenAI visuals stay off by default.
- [x] `.github/dependabot.yml` adds a `package-ecosystem: pip` (or `uv`) group covering the project dependencies.
- [x] CONTRIBUTING runbook section explicitly documents the OpenAI-disabled default and the override contract.

---

## Steps

### Step 1 — Single Sanitize Chokepoint

- [x] Introduce the redaction module and migrate the four call sites to delegate.
- [x] Resolve DEBT-035 / DEBT-036 / DEBT-042 in `docs/TECH-DEBT.md`.

### Step 2 — OpenAI Env Integration

- [x] Add `OPENAI_API_KEY` to preflight required-vars list with a "disabled by default" code path.
- [x] Extend the literal redaction list to cover OpenAI key shapes.
- [x] Update GHA workflow to force `INVESTO_OPENAI_VISUALS=0` (or fail closed).

### Step 3 — Dependabot and Runbook

- [x] Add the `pip`/`uv` dependabot group.
- [x] Document the OpenAI-disabled default and override path in CONTRIBUTING runbook.

### Step 4 — Verification

- [x] Add a regression test that asserts the four call sites all route through the chokepoint.
- [x] Run targeted redaction/preflight tests and the full quality gate.

---

## Source

Persona evaluation 2026-05-07: persona #5 (P0). Recovers DEBT-035 / DEBT-036 / DEBT-042.
