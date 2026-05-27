"""Reader-experience enhancement (u83 decomposition — internal).

Cohesive home for the briefing's *reader-facing presentation* split out
of the former ``briefing/pipeline.py`` god-module:

* :mod:`coverage_badge` — coverage badge + failure-reason classification.
* :mod:`context_render` — recent / carryover / bundle / lookahead /
  segment-scope context-block rendering (the SINGLE home for
  context-block rendering, per the u83 plan correction).
* :mod:`enhancement` — ``_enhance_reader_experience`` header assembly
  (title, nav, watermark, summary, badges) + the data-limited body.
* :mod:`lineage` — ``_macro_lineage_*`` signal builders that feed the
  existing :mod:`investo.briefing.lineage` trace builder.

Briefing-internal (no module-boundary concern). Public symbols keep
their import path via re-export from ``briefing/pipeline.py``.
"""

from __future__ import annotations
