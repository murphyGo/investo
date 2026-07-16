"""Canonical namespace constants for RSS/Atom/Dublin-Core elements consumed by source adapters.

Add new constants here as adapters need them; don't pre-add unused ones.
"""

from __future__ import annotations

from typing import Final

DC_CREATOR: Final[str] = "{http://purl.org/dc/elements/1.1/}creator"
NASDAQ_TICKERS: Final[str] = "{http://nasdaq.com/reference/feeds/1.0}tickers"

# Atom 1.0 default namespace (Clark notation) — SEC EDGAR 8-K + Treasury feeds.
ATOM_NS: Final[str] = "{http://www.w3.org/2005/Atom}"

# Microsoft ADO dataservices namespaces used by the Treasury Atom feed's
# <m:properties> / <d:*> rate fields.
DATASERVICES_M_NS: Final[str] = "{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}"
DATASERVICES_D_NS: Final[str] = "{http://schemas.microsoft.com/ado/2007/08/dataservices}"

# Media RSS namespace (Clark notation) — <media:content> / <media:thumbnail>
# / <media:credit> image references carried by the Yonhap, Yahoo Finance and
# The Block news feeds (u136 feed-image-metadata-harvest).
MEDIA_NS: Final[str] = "{http://search.yahoo.com/mrss/}"
MEDIA_CONTENT: Final[str] = MEDIA_NS + "content"
MEDIA_THUMBNAIL: Final[str] = MEDIA_NS + "thumbnail"
MEDIA_CREDIT: Final[str] = MEDIA_NS + "credit"
