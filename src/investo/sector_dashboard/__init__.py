"""Private, deterministic sector-dashboard component (u139).

Runtime behavior is added stepwise under this package.  The component may depend on
``investo.models`` but never on Investo's briefing, source, publisher, notifier, or
scheduled orchestration components.
"""

from investo.sector_dashboard.hf_data import (
    DEFAULT_HF_ADAPTER_CONFIG,
    HFAdapterConfig,
    HFRequestBudget,
    collect_public_bars,
    compute_hf_retry_delay,
)
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
from investo.sector_dashboard.private_render import (
    PrivateCommitResult,
    PrivateOutputRejectedError,
    PrivateOutputSession,
    PrivateTransactionError,
    RenderedPrivateProjection,
    open_private_output_session,
    render_private_projection,
    verify_private_projection,
)
from investo.sector_dashboard.public_metrics import (
    build_public_series_bundle,
    compute_public_sector_metrics,
    compute_public_sector_snapshot,
    resolve_public_freshness,
)
from investo.sector_dashboard.public_render import (
    MAX_PUBLIC_PROJECTION_BYTES,
    PublicProjectionError,
    render_public_sector_projection,
    verify_public_sector_projection,
)
from investo.sector_dashboard.public_store import (
    PUBLIC_MARKDOWN_NAME,
    PUBLIC_SECTOR_DIRECTORY,
    PUBLIC_SNAPSHOT_NAME,
    PublicSectorStoreError,
    hold_public_sector_last_good,
    promote_public_sector_projection,
    read_public_sector_projection,
)
from investo.sector_dashboard.regime import (
    classify_regime_history,
    classify_sector_regime,
    neutral_band_ratio,
    regime_policy_for_band,
    resolve_axis_state,
)

__all__ = [
    "DEFAULT_HF_ADAPTER_CONFIG",
    "MAX_PUBLIC_PROJECTION_BYTES",
    "PUBLIC_MARKDOWN_NAME",
    "PUBLIC_SECTOR_DIRECTORY",
    "PUBLIC_SNAPSHOT_NAME",
    "HFAdapterConfig",
    "HFRequestBudget",
    "PrivateCommitResult",
    "PrivateInputError",
    "PrivateOutputRejectedError",
    "PrivateOutputSession",
    "PrivateTransactionError",
    "PublicProjectionError",
    "PublicSectorStoreError",
    "RenderedPrivateProjection",
    "build_public_series_bundle",
    "classify_regime_history",
    "classify_sector_regime",
    "collect_public_bars",
    "compute_hf_retry_delay",
    "compute_public_sector_metrics",
    "compute_public_sector_snapshot",
    "compute_relative_ranks",
    "compute_sector_metrics",
    "compute_sector_snapshot",
    "descending_midrank_percentiles",
    "hold_public_sector_last_good",
    "load_private_nav_workbooks",
    "nav_excess_return",
    "nav_max_drawdown_20d",
    "nav_realized_volatility_20d",
    "nav_relative_acceleration_5d",
    "nav_return",
    "neutral_band_ratio",
    "open_private_output_session",
    "parse_private_nav_workbooks",
    "promote_public_sector_projection",
    "read_private_workbook_manifest",
    "read_public_sector_projection",
    "regime_policy_for_band",
    "render_private_projection",
    "render_public_sector_projection",
    "resolve_axis_state",
    "resolve_public_freshness",
    "verify_private_projection",
    "verify_public_sector_projection",
]
