# Code Generation Plan: `u10 source-coverage-diagnostics`

**Date**: 2026-05-07
**Unit**: u10 source-coverage-diagnostics
**Stage**: Code Generation

---

## Goal

Make source coverage visible in GitHub Actions logs so the operator can distinguish a failed source from a successful source that returned zero items for the selected market window.

---

## Definition of Done

- [x] Successful adapters emit one structured INFO log line.
- [x] The log includes source name, category, item count, and UTC window bounds.
- [x] Zero-item successes are logged separately from warnings for failures.
- [x] GitHub Actions plain-text logs render the diagnostic fields without a custom formatter.
- [x] Existing failure-isolation behavior remains unchanged.

---

## Steps

### Step 1 — Aggregator Success Logs

- [x] Add `source returned` INFO log after each successful adapter result.
- [x] Include `source_name`, `category`, `item_count`, `window_start_utc`, and `window_end_utc` in `extra`.

### Step 2 — Regression Tests

- [x] Test non-empty success logging.
- [x] Test zero-item success logging.
- [x] Re-run aggregator tests.

### Step 3 — Plain-Text GHA Readability

- [x] Render source name, category, item count/window, transient flag, and error in the log message text.
- [x] Keep structured `extra` fields for future log processors.
- [x] Update log assertions so the default GitHub Actions formatter remains covered.
