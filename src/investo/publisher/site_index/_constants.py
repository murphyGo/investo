"""Shared path/marker constants for the site_index package surfaces.

Move-only from the original ``site_index.py`` module. The canonical
public-facing constants are re-exported verbatim from the package
``__init__``; surface modules import them from here to avoid an import
cycle through the package root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
)

SITE_INDEX_PATH: Final[Path] = Path("site_docs/index.md")
ARCHIVE_INDEX_PATH: Final[Path] = Path("archive/index.md")
# u32 Step 4 — public quality dashboard. Lives under ``site_docs/`` so
# mkdocs picks it up alongside the other top-nav pages. The page is
# regenerated on every successful publish; an absent file (first
# publish on a fresh checkout) gets created lazily.
QUALITY_PAGE_PATH: Final[Path] = Path("site_docs/quality.md")
ACCURACY_PAGE_PATH: Final[Path] = Path("site_docs/accuracy.md")
SEGMENT_ARCHIVE_INDEX_PATHS: Final[dict[MarketSegment, Path]] = {
    DOMESTIC_EQUITY: Path("archive/domestic-equity/index.md"),
    US_EQUITY: Path("archive/us-equity/index.md"),
    CRYPTO: Path("archive/crypto/index.md"),
}
_SEGMENTS: Final[tuple[MarketSegment, ...]] = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)

HERO_BEGIN: Final[str] = "<!-- u29 hero begin -->"
HERO_END: Final[str] = "<!-- u29 hero end -->"
HEATMAP_BEGIN: Final[str] = "<!-- u29 heatmap begin -->"
HEATMAP_END: Final[str] = "<!-- u29 heatmap end -->"

# Surface-specific fallback text — the chokepoint helper
# (:func:`investo.briefing.extract.extract_conclusion`) returns ``None``
# on miss and each surface owns its own fallback wording (DEBT-060
# consolidation 2026-05-08).
_HERO_FALLBACK_TEXT: Final[str] = "결론 인용을 추출하지 못했습니다."
