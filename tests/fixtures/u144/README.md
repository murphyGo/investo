# u144 incident fixtures

These fixtures preserve the minimum public-document shapes needed to reproduce
the three mutation-order incidents that motivated u144. They are deliberately
redacted:

- no raw collected payloads, credentials, repository URLs, or notification
  destinations are copied from production;
- market values and source item text are replaced with deterministic examples;
- GitHub Actions metadata is limited to the run/date/segment and bounded public
  outcome codes needed to identify the incident;
- `markdown_before_*` and `markdown_after_*` fields isolate the producer/gate
  mismatch instead of pretending to be complete market briefings.

Characterization tests should load these JSON files as immutable inputs. Later
u144 regression tests may assert the new finalizer outcome against the same
fixtures without rewriting the incident baseline.

The two `legacy-*-partial.json` fixtures are intentionally separate even
though the current `PipelineResult` collapses both to `status=partial` and the
CLI maps both to exit 0. One represents u63/u94 valid-subset publication; the
other represents complete content followed by a notifier-only failure. U144
will change the first path's signaling without changing the second.
