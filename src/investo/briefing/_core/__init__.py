"""Briefing pipeline core stages (u83 decomposition — internal).

Cohesive home for the briefing's *control-flow* responsibilities split
out of the former ``briefing/pipeline.py`` god-module:

* :mod:`classification` — Stage 1 output model + JSON load / recovery /
  inversion-flip parsing.
* :mod:`section_planning` — ``SectionPlan`` + ``build_section_plan``.
* :mod:`orchestration` — the ``_classify`` / ``_synthesize`` retry-budget
  loops and the per-run ``GenerationPolicy``.

This sub-package is briefing-internal (no module-boundary concern). The
public symbols keep their import path via re-export from
``briefing/pipeline.py``.
"""

from __future__ import annotations
