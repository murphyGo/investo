# u145 — final integration and public rollout

## Authorization and scope

The user requested `공개까지 완료 진행해줘` after the status audit confirmed that
the implementation existed on a local branch but the public `/investo/sectors/`
route returned HTTP 404. This authorizes final main integration, scoped commit/push,
public Pages deployment and the dedicated automatic refresh workflow.

The isolated `.tmp/u145-publish-20261010` worktree starts from current remote main
`e9fb0c9c49308788871c49eedec5bf6efe498126` and merges activation head
`6b371a1cc842ae33aef08f0d51ff01774b995df3`. The original dirty root, the activation
worktree and its four unfinished documents are preserved. The merge retains both
`COINGECKO_DEMO_API_KEY` and historical `HF_DATA_API_KEY` redaction entries and tests.
Concurrent u154/u163–u166 code, state and audit records are retained.

The existing Yahoo public-use operator exception and the explicit Browser
`WAIVED / NOT_EXECUTED` decision remain recorded. Free, keyless, derived-only data,
freshness, canonical identity and transactional last-good rules remain binding.

## Local evidence

- Frozen dev/docs/sector installation: successful.
- Ruff check and format: PASS, 706 Python files.
- Strict mypy: PASS, 302 source files.
- No-Anthropic, no-paid/provider, curated-assets and image-store guards: PASS.
- Maximum-size synthetic input: PASS, 12 requests, 1 MiB each, 140 rows per series;
  wall 2,419 ms, CPU 1,392 ms, incremental peak RSS 70,369,280 bytes.
- Actual public build: `promoted`, normal, fresh completed NYSE session
  **2026-10-08**, 12/12 successful requests, 11/11 available/comparable sectors,
  no failures; collection 1,526 ms, total 8,494 ms, CPU 6,959 ms.
- Exact derived pair passes canonical verification; snapshot
  `sha256:6ac61b30de1c6133f411bb16e426a42d89ee727640dcb4f2bf188ddb0e9057f8`.

Final full regression, independent release review, remote SHA/CI, refresh run,
Pages deployment and live canonical HTML/JSON evidence are pending.

## Operational contract

Public destination: <https://murphygo.github.io/investo/sectors/>.
Refresh uses the dedicated main-only `sector-dashboard.yml`, Monday–Friday
21:35 UTC (Tuesday–Saturday 06:35 Asia/Seoul). The same workflow is manually
dispatched for first operational verification. It stages exactly the two derived
sector files and explicitly dispatches Pages after validation. Failed collection
retains the last verified date and identity; partial publication remains explicit.

No unrelated runtime activation, model invocation, Telegram delivery or historical
briefing republish is included in this rollout.

References: [activation implementation](2026-10-06-u145-public-activation.md),
[cross-check](../cross-checks/2026-10-06-u145-public-activation.md),
[runbook](../sector-dashboard-public-runbook.md).
