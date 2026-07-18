"""Private, deterministic sector-dashboard component (u139).

Runtime behavior is added stepwise under this package.  The component may depend on
``investo.models`` but never on Investo's briefing, source, publisher, notifier, or
scheduled orchestration components.
"""

from investo.sector_dashboard.private_input import (
    PrivateInputError,
    load_private_nav_workbooks,
    parse_private_nav_workbooks,
    read_private_workbook_manifest,
)

__all__ = [
    "PrivateInputError",
    "load_private_nav_workbooks",
    "parse_private_nav_workbooks",
    "read_private_workbook_manifest",
]
