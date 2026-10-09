# u163 implementation

2026-10-09. User authorized development and per-unit commit/push. Code validation complete; scheduled recovery acceptance remains pending.

Split-sign emphasis is repaired without changing digits, separators, currencies, units or signs. Ambiguous numeric syntax stays blocked. The existing finalizer and its numeric evidence/content gates are unchanged. Repair precedes the last numeric styling pass; styling cannot rewrap a numeric prefix inside valid bold text. Fully assembled three-market bundles, notification summaries and carryover supplements retain stable text and hashes on repeated finalization.

Code, links (inline/reference/shortcut/image/autolink), table rows, diagnostics and disclaimers are protected at the repair boundary. Existing first-viewport trace rejection, including escaped assignments and inline-code assignments, remains intentional. Independent review found and prompted fixes for normal-link trace repair, shortcut references and case-varied autolinks; final review and full gate results are recorded in the session/cross-check.

Files: `_internal/surface_quality.py`, `publisher/segment_reader_format.py`, `publisher/reader_format/emphasis.py`; regression suites `test_numeric_emphasis_u163.py` and `test_numeric_emphasis_containment_u163.py`. Hypothesis checks 150 numeric invariant/idempotence examples. Focused seven-suite validation:428 passed. No HTTP, dependency, source registration, model call, runtime pin, publication retry or cost change.

Final validation:6256 passed/485.42s after integrating concurrent eea56bd0; independent479 passed/14.69s and review CLOSED. Ruff/format671, mypy290, four existing policy guards, strict docs/Material and diff checks PASS. The early pass is numeric-only so empty summary fallbacks retain their original owner; two observer tests forward that optional mode. Earlier full failures were fixed and are not counted as passes.

Exact rejected production text was not recovered; synthetic characterization is not an exact incident replay. Ten distinct scheduled runs on a reviewed runtime pin are still required for operational closeout.
