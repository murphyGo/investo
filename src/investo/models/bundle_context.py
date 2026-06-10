"""BundleContext + MarketStateSummary — u57 same-bundle reconciliation.

Foundation-level model. Lives under :mod:`investo.models` because all
three sibling units (orchestrator, briefing, publisher) consume it:

* ``orchestrator`` builds it (``orchestrator.bundle_context``) right
  after routing.
* ``briefing`` injects it into the Stage-2 prompt so each segment knows
  the same-run market state of the *other* two segments.
* ``publisher`` consumes it during the cross-segment lint chain
  (``publisher.cross_segment_lint``).

The pre-computation pattern (Option B from the u57 plan) decouples
prompt content from ``SEGMENT_ORDER``: each segment receives a snapshot
of all three close-states *before* any segment is generated. The
segment's *own* slot is intentionally pinned to ``pending`` so the
prompt cannot self-assert "I'm already closed" (anti-regression).

References
----------

* u57 plan Step 1.5 — BundleContext pre-computation.
* u57 DoD — "BundleContext (same-run, per-segment market-state summary)
  is computed before Stage 2 and injected as the same object into all
  three prompts".
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from investo.briefing.time_state import TimeState

# Re-exported under :mod:`investo.models` so consumers do not have to
# reach into ``briefing`` for the literal alias.
__all__ = [
    "CROSS_MARKET_CORE_ALLOWED",
    "BundleContext",
    "CloseState",
    "DailyThesisDecision",
    "DailyThesisSignal",
    "MarketStateSummary",
]


# A segment can resolve to any of the six time-state labels *or* to the
# sentinel ``"pending"``. The sentinel applies to (a) the segment's own
# slot during its own prompt build (anti-self-assertion) and (b) any
# segment whose routed items contain zero time-state-bearing titles.
CloseState = TimeState | Literal["pending"]
DailyThesisMode = Literal["strong", "data_limited", "omit"]


# Cross-market themes allowed to remain at §② core tier even when they
# are not segment-native. Anything outside this allow-list gets demoted
# to background by the lint chain (u57 plan Step 4).
#
# 신규 항목 추가는 별 unit 임 — 이 frozenset 은 single source of truth
# 로 prompt + lint 양쪽이 참조한다. 변경 시 회귀 영향 평가 필수.
CROSS_MARKET_CORE_ALLOWED: Final[frozenset[str]] = frozenset(
    {
        "geopolitical_oil_macro",
        "fed_policy_event",
        "global_systemic_risk",
    }
)


class MarketStateSummary(BaseModel):
    """Per-segment same-run market state snapshot.

    Immutable. Carries the *factual* close-state the segment finished
    the day in (per the most recent freshness-ranked native source
    item) plus a one-line headline fact the LLM can quote without
    re-fetching.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    segment: str = Field(min_length=1, max_length=64)
    target_date: date
    tz: str = Field(min_length=1, max_length=32)
    close_state: CloseState
    headline_native_fact: str | None = None


class DailyThesisSignal(BaseModel):
    """One deterministic signal eligible for the same-run thesis layer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    segment: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=64)
    tier: str = Field(min_length=1, max_length=32)
    evidence_label: str = Field(min_length=1, max_length=120)
    source_ids: tuple[str, ...] = ()


class DailyThesisDecision(BaseModel):
    """Final same-run thesis decision rendered by the publisher."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: DailyThesisMode
    line: str | None = None
    macro_keys: tuple[str, ...] = ()
    supporting_segments: tuple[str, ...] = ()
    reason: str = Field(min_length=1, max_length=120)


class BundleContext(BaseModel):
    """Same-run reconciliation snapshot — shared by all three segments.

    The bundle id is the orchestrator's run identifier (typically the
    archive date + a short hash); it exists so structured logs can
    associate lint violations with the run that produced them.

    ``shared_macro_block`` is the rendered ``## ⓪ 오늘의 매크로`` H2
    body (1 paragraph) when at least one global macro fact (UST yield,
    Brent/WTI, FOMC schedule) appears in two or more segments' routed
    items. ``None`` when no shared macro was detected.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle_id: str = Field(min_length=1, max_length=128)
    target_kst_date: date
    segments: dict[str, MarketStateSummary] = Field(default_factory=dict)
    shared_macro_block: str | None = None
    cross_market_core_allowed: frozenset[str] = Field(
        default=CROSS_MARKET_CORE_ALLOWED,
    )
    daily_thesis_signals: tuple[DailyThesisSignal, ...] = ()
    daily_thesis_decision: DailyThesisDecision = Field(
        default_factory=lambda: DailyThesisDecision(mode="omit", reason="not_evaluated"),
    )

    def for_segment(self, segment: str) -> MarketStateSummary | None:
        """Return the summary for ``segment`` or ``None`` if missing."""
        return self.segments.get(segment)

    def with_self_pending(self, segment: str) -> BundleContext:
        """Return a copy where ``segment``'s close_state is forced to ``pending``.

        Used by the per-segment prompt builder: when generating
        segment X's narrative we do not want X's own slot to assert
        "closed at +0.5%" — that would invite the LLM to circular-cite
        its own draft. The other two segments retain their factual
        close-state.
        """
        if segment not in self.segments:
            return self
        current = self.segments[segment]
        if current.close_state == "pending":
            return self
        rewritten = dict(self.segments)
        rewritten[segment] = current.model_copy(update={"close_state": "pending"})
        return self.model_copy(update={"segments": rewritten})
