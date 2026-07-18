"""Private, deterministic sector-dashboard component (u139).

Runtime behavior is added stepwise under this package.  The component may depend on
``investo.models`` but never on Investo's briefing, source, publisher, notifier, or
scheduled orchestration components.
"""

from investo.sector_dashboard.metrics import (
    compute_relative_ranks,
    compute_sector_metrics,
    compute_sector_snapshot,
    descending_midrank_percentiles,
    nav_excess_return,
    nav_max_drawdown_20d,
    nav_realized_volatility_20d,
    nav_relative_acceleration_5d,
    nav_return,
)
from investo.sector_dashboard.private_input import (
    PrivateInputError,
    load_private_nav_workbooks,
    parse_private_nav_workbooks,
    read_private_workbook_manifest,
)
from investo.sector_dashboard.regime import (
    classify_regime_history,
    classify_sector_regime,
    neutral_band_ratio,
    regime_policy_for_band,
    resolve_axis_state,
)

__all__ = [
    "PrivateInputError",
    "classify_regime_history",
    "classify_sector_regime",
    "compute_relative_ranks",
    "compute_sector_metrics",
    "compute_sector_snapshot",
    "descending_midrank_percentiles",
    "load_private_nav_workbooks",
    "nav_excess_return",
    "nav_max_drawdown_20d",
    "nav_realized_volatility_20d",
    "nav_relative_acceleration_5d",
    "nav_return",
    "neutral_band_ratio",
    "parse_private_nav_workbooks",
    "read_private_workbook_manifest",
    "regime_policy_for_band",
    "resolve_axis_state",
]
