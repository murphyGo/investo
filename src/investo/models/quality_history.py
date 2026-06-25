"""Quality-history value objects shared by publisher and visuals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class QualityHistoryRow:
    """One slot in the rolling quality-history window."""

    day: date
    source_liveness: float | None = None
    figures_presence: float | None = None
    fallback_ratio: float | None = None
    published_segments: int | None = None
    total_items: int | None = None
    total_failed_sources: int | None = None
    worst_severity: str | None = None
    figures_verified: float | None = None
    macro_actual_missing_segments: int | None = None
    required_macro_omitted: int | None = None
    current_run_zero_item_sources: int = 0
    current_run_core_missing_segments: int = 0
    current_run_segments_limited_or_worse: int = 0
    current_run_data_limited_briefings: int = 0
    current_run_briefings_observed: int = 0

    @property
    def has_data(self) -> bool:
        return (
            self.source_liveness is not None
            and self.figures_presence is not None
            and self.fallback_ratio is not None
        )


__all__ = ["QualityHistoryRow"]
