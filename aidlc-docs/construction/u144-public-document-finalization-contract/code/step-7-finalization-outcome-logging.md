# Step 7 production replay: finalization outcome logging

## Production evidence

Exact-date run `29897137121` at head `fb09360` verified that supplement
preservation fixed the preceding zero-survivor defect:

- generation completed with `ok=3 failed=0`;
- domestic equity and crypto finalized, were written, and were committed and
  pushed together as `c83fac3`;
- US equity was withheld by a terminal trust gate;
- the notifier succeeded (`message_id=73`);
- the pipeline reported `status=partial` and exit code 2;
- Pages dispatch ran before the red conclusion, and Pages run `29898005248`
  succeeded for `c83fac3`.

This is the intended AC-144.8 partial-publication sequence. It does not yet
satisfy AC-144.14 because the exact-date closeout requires all three segments.

## Diagnostic gap

The bounded segment outcome codes were written to the GitHub step summary but
not to the downloadable execution log. `PublishStage` retained only the
blocked segment names in stage notes. Consequently, a live partial run could
prove correct containment but could not identify the specific terminal trust
gate from the retained log.

## Repair

Immediately after pure finalization returns, `PublishStage` now emits one INFO
record per expected segment:

```text
[finalize] target_date=<date> segment=<segment> state=<state> codes=<codes|none>
```

Values come exclusively from validated `SegmentFinalizationOutcome` fields.
No generated Markdown, evidence preview, URL, source payload, or secret enters
the log. The pure finalizer remains free of logging and other I/O.

## Validation

- PublishStage outcome/log regression: 3 passed.
- Combined orchestrator result/CLI/pipeline scope: 167 passed.
- Ruff check passed; Ruff format passed after formatting the test.
- Strict mypy passed for `orchestrator/pipeline.py`.

The next exact-date replay will expose any remaining US trust-gate code in the
retained log and must still publish all three segments before closeout.
