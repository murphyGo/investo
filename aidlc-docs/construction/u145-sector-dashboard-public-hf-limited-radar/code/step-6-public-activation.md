# Step 6 — public Yahoo sector activation

The user's continuation after Step 5 authorized main integration, Pages publication and
scheduling. The qualified probe-only commit `ec7ac84b` and activation `1a753c7c` are separate;
independent review repair `6b371a1c` fixes unsupported-calendar last-good reporting.

## Composition and publication boundary

`public_build.build_public_sector` composes the qualified bounded Yahoo collector, close-only
bundle, deterministic snapshot, renderer and recoverable store. Only a fresh snapshot matching
the completed target session with normal/partial coverage can promote. Measured collection/CPU
overruns, stale/warming/insufficient data and exceptions use a closed hold/block outcome.
`hold_failed_public_build` also handles pre-network calendar failure: valid prior pair means
`held_last_good`; absent/corrupt prior state means `blocked`.

The separate fixed-mode `publish_sector_dashboard.py` accepts `--write` or `--verify-only`.
The probe CLI still accepts only `--probe-only` and cannot write public files. Both share the
same bounded secret-screened summary helper. GitHub control output is emitted only after
screening. Normal promoted/unchanged results exit 0; partial and failed attempts exit 2.

The dedicated main-only workflow runs weekdays UTC 21:35. It validates the pair and strict
site before staging exactly the two derived files. Normal non-fast-forward rejection leaves
remote main unchanged; a fresh run recollects instead of merging old snapshots. Explicit Pages
dispatch handles GitHub token push suppression, and valid unchanged reruns support deployment
recovery. Partial publication dispatches before the final nonzero status. Pages independently
checks canonical integrity before build/deploy. Telegram and daily briefing remain separate.

## Verification and operation

Tests exercise real collector/metrics/render/store composition with synthetic HTTP, including
fresh, unchanged, transient partial, auth last-good, first failure, stale/short history, CPU/
wall budget, damaged store, secret output, invalid CLI arguments and unsupported calendar.
The actual workflow git script is executed against isolated local remotes to test pair-only
staging, no-op commits and concurrent-main rejection. u139's guard permits only exact public
commands in designated workflows; private no-network and public non-interference remain.

The page includes all eleven sectors and generation-time freshness. The initial pair is real
derived Yahoo data, not a placeholder. Static semantic/HTML integrity tests are distinct from
the user's **WAIVED / NOT_EXECUTED** browser viewport acceptance. Public permission remains
unverified under the existing operator exception.

Operational evidence and final status:
`docs/sessions/2026-10-06-u145-public-activation.md`.
Complete amended R/AC mapping:
`docs/cross-checks/2026-10-06-u145-public-activation.md`.
Run/recovery/disable procedure:
`docs/sector-dashboard-public-runbook.md`.
