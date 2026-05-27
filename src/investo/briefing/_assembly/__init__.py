"""Briefing assembly helpers (u83 decomposition — internal).

Cohesive home for the briefing's *text-shaping* responsibilities split
out of the former ``briefing/pipeline.py`` god-module:

* :mod:`text_normalize` — six-section parsing + summary-line cleanup +
  sentence splitting.
* :mod:`summary_extraction` — first-viewport summary sentence + header.
* :mod:`markdown_render` — Stage 2 grouped/unassigned/required-macro
  bullet rendering (LLM-input rendering of classified evidence).
* :mod:`prompt_fields` — prompt-field truncation + URL shaping (an
  LLM-INPUT concern, deliberately distinct from output rendering).

Briefing-internal (no module-boundary concern). Public symbols keep
their import path via re-export from ``briefing/pipeline.py``.
"""

from __future__ import annotations
