# Application Design Plan: 미국 섹터 core radar

**Date**: 2026-07-18
**Status**: Complete for unit registration
**Source**: approved product decisions and S0 source decision

## Decision Inputs

- Existing GitHub Pages is the public target; private validation is allowed while the source gate is blocked.
- Core radar precedes actual flow and earnings actuals.
- Telegram follows web stabilization.
- Public price data must have explicit public derived-display rights.
- The user explicitly approved proceeding with S0-P Application Design and registering a price-data problem unit on 2026-07-18.

No unanswered design question remains at this stage. Provider selection is intentionally owned by the blocked source-qualification unit rather than guessed in Application Design.

## Plan

- [x] Load product plan, S0 decision, requirements, stories, current component design, and source registry context.
- [x] Define the `sector_dashboard` component responsibility without changing the existing import DAG.
- [x] Define high-level private input, deterministic metric, regime, snapshot, and local-render interfaces.
- [x] Define the private-validation service boundary and fail-closed public source gate.
- [x] Update component dependency and consolidated Application Design artifacts.
- [x] Register `u139 sector-dashboard-private-core-radar-validation`.
- [x] Register `u140 sector-dashboard-public-ohlcv-source-qualification` separately from `u138` endpoint repair.
- [x] Update FR/NFR and story traceability.
- [x] Validate unit independence: u139 does not wait for u140; public construction waits for both u139 domain validation and u140 source qualification.
- [x] Record the user's approval and stage outcome in the audit log.

## Stage Outcome

- `u138`: repairs current production price endpoint lifecycle; does not grant public sector-data rights.
- `u139`: validates domain math and UI contracts with local/private NAV input only.
- `u140`: remains blocked until a terms-compliant 11-sector + SPY OHLCV source clears the public gate; completing both u139 and u140 is the prerequisite for later public construction units.

## Stage Closeout

- [ ] Request Changes
- [x] Continue to Next Stage
