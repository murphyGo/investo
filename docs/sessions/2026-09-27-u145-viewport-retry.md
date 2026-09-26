# Session Log: 2026-09-27 — u145 viewport retry

## Result

The user requested `u145 대시보드 화면 검증 이어서 진행`.
Step 4 actual viewport acceptance remains **NOT_EXECUTED** because Browser startup fails.
The five synthetic previews were rebuilt and are ready for visual inspection after recovery.

## Preserved implementation

Work continued in `.tmp/u145-resume-20260922`, branch `codex/u145-resume-20260922`,
base `c286f5003973c3d7a5fc0c7db2eeda0e6e9bb64c`, with its existing Step 1–4 overlay.
No application code, dependency, test, or production workflow was changed this session.
The unrelated dirty root worktree was preserved. Its observed HEAD was `985b7e40`;
this retry does not claim integration or validation against that newer root HEAD.

## Current Browser evidence

- The official Browser client failed before discovery with `Cannot find module` for
  `/Users/user/.codex/plugins/cache/openai-bundled/browser/26.915.31945/scripts/browser-service.mjs`.
- A filesystem check confirmed that referenced version and service file are absent.
- The readable cached Browser skill/client belongs to version `26.814.41407`.
- The official `check-native-host-manifest.js --browser chrome --json` diagnostic exited 1:
  `exists=false`, `correct=false`, with Chrome's `com.openai.codexextension.json` missing.
- Plugin directory discovery did not return a supported repair capability for the bundled
  Browser. No unrelated browser integration was installed or substituted.
- The user was asked to reinstall Browser through the app UI and fully restart Codex/Chrome.
  The Browser skill's referenced `docs/chrome-troubleshooting.md` says:
  "Do not install or repair the native host yourself."

No screenshot or actual viewport measurement was produced. This is an environment failure,
not evidence that the dashboard's visual layout passed or failed.

## Completed preparation

Command run successfully from the preserved worktree:

```sh
uv run --frozen --extra dev --extra docs --extra sector python .tmp/u145-viewport-check/prepare.py
```

- Strict MkDocs build and canonical Markdown/JSON pair verification passed for all five states.
- Static HTML checks passed: responsive viewport metadata, eleven sector rows, first four
  headers in the approved order, explicit XLRE unavailability, and IEX qualification before
  the table.
- `.tmp/u145-viewport-check/evidence.json` records the snapshot identities, HTML/source hashes,
  `synthetic_only=true`, and `viewport_acceptance=NOT_EXECUTED`.
- Renderer SHA-256: `55d34fcd600bc173ed9571094820bc570c7833fb569e2ab7626ca83015cdddbf`.
- A loopback-only preview server was started on port 8145 after sandbox escalation approval.
  Each of `fresh`, `partial`, `warming`, `insufficient`, and `stale` returned HTTP 200.
  Server availability is session-bound and must be rechecked after restarting Codex.

The prior full test run remains historical evidence from 2026-09-22; it was not rerun for
this preview rebuild and documentation-only retry.

## Pending visual acceptance matrix

Every cell below requires an actual Browser screenshot and inspection. Desktop 1280×720 is
the selected desktop test size; the binding NFR also requires mobile 390×844.

| Synthetic state | 390×844 light | 390×844 dark | 1280×720 light | 1280×720 dark |
| --- | --- | --- | --- | --- |
| fresh | Not executed | Not executed | Not executed | Not executed |
| partial (eight sectors) | Not executed | Not executed | Not executed | Not executed |
| warming | Not executed | Not executed | Not executed | Not executed |
| insufficient | Not executed | Not executed | Not executed | Not executed |
| stale | Not executed | Not executed | Not executed | Not executed |

Check the visible limitation banner, freshness and coverage text, first four table columns,
table scrolling without page-level clipping, all eleven sector identities, textual distinction
between unsupported and transiently unavailable sectors, readable contrast in both themes,
and descriptive HF/IEX attribution links. Verify warming and invalid states suppress the
summary/rank/regime as specified. The synthetic insufficient/stale renderer previews do not
constitute public-store promotion or last-good delivery-wrapper acceptance.

After Browser recovery, reuse this worktree and start at
`http://127.0.0.1:8145/u145-preview/fresh/`. Rebuild and restart the documented local server if
needed. Record actual visual evidence before marking the Step 4 checkbox complete.

Step 5 probes and Step 6 activation remain unstarted. No live HF request, public-sector write,
navigation change, deployment, Telegram send, commit, or push was made.
