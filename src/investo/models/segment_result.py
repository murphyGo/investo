"""u55 Step 4 — Per-segment publish status contract.

Publisher contract change (FR-011): orchestrator emits one
:class:`SegmentResult` per segment instead of a raw ``SegmentBriefing |
None``. Only ``status == "fresh"`` segments land in the archive +
Telegram public channel; ``stale`` / ``failed`` surfaces on the quality
page and as an operator alert (FR-007) — no public publish.

Why a separate model rather than overloading ``SegmentBriefing``:

* **Frozen contract**. Publisher / notifier / quality reader all
  branch on ``status`` only; the briefing payload (if any) is the
  side-payload. Mixing the two on one model bleeds publish-policy
  state into briefing data.
* **Graceful degradation**. A ``stale`` segment publishes its
  ``stale_reason`` to the quality page without a briefing body — the
  reader sees "오늘은 갱신 안 됨" rather than yesterday's content
  silently re-served.

Module boundary: foundation under ``models/``. Imports only
:mod:`investo.models.briefing` (sibling).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from investo.models.briefing import Briefing

# Re-declared as a Literal (not imported from briefing/segments) to keep
# the foundation-layer rule — ``models/`` does not import from
# ``briefing/``. The value strings match
# :data:`briefing.segments.MarketSegment` byte-for-byte.
Segment = Literal["domestic-equity", "us-equity", "crypto"]

# ``fresh`` — segment has a publishable briefing for today.
# ``stale`` — latest archive is older than the calendar expected;
#             quality page lists it; public channel skips.
# ``failed`` — generation or upstream gate (numeric / direction) failed;
#              same surface as ``stale`` for the reader, but the
#              operator alert carries the failure reason.
SegmentStatus = Literal["fresh", "stale", "failed"]


class SegmentResult(BaseModel):
    """One segment's publish-eligibility decision.

    Invariants enforced by ``model_validator``:

    * ``status == "fresh"`` ⇒ ``briefing is not None``.
    * ``status in {"stale", "failed"}`` ⇒ ``briefing is None``.
    * ``stale_reason`` is required when ``status != "fresh"`` and
      forbidden when ``status == "fresh"``.

    The reason text is human-readable Korean (rendered verbatim on the
    quality page). Avoid embedding raw error messages — those are
    operator-alert payloads, not reader-facing copy.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    segment: Segment
    status: SegmentStatus
    briefing: Briefing | None = None
    stale_reason: str | None = None

    @model_validator(mode="after")
    def _enforce_contract(self) -> SegmentResult:
        if self.status == "fresh":
            if self.briefing is None:
                raise ValueError("SegmentResult.fresh requires briefing")
            if self.stale_reason is not None:
                raise ValueError("SegmentResult.fresh forbids stale_reason")
        else:
            if self.briefing is not None:
                raise ValueError(f"SegmentResult.{self.status} forbids briefing")
            if not self.stale_reason:
                raise ValueError(f"SegmentResult.{self.status} requires stale_reason")
        return self

    @property
    def is_publishable(self) -> bool:
        """``True`` iff this segment should reach the public channel."""
        return self.status == "fresh"


__all__ = [
    "Segment",
    "SegmentResult",
    "SegmentStatus",
]
