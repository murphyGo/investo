# u176 Business logic model

2026-10-10. User authorized all UI development; the following are developer-selected concrete decisions, not individually answered user preferences. No event-v3 semantic API is assumed implemented.

MkDocs uses its existing page metadata/`page.file.src_uri` to classify `index.md` as home, dated archive pages as article, and other pages as reference. A scoped content wrapper carries that class. Desktop home hides only its own sidebars; mobile primary drawer remains native Material. Other pages retain navigation/TOC and a76ch reading width. A keyboard adapter makes existing header labels reachable buttons without changing their checkbox/radio state owner. Escape closes native search/drawer and restores focus. Native labels/static navigation keep links reachable with JS disabled.

Navigation order: 최신 시황 → 관심 자산 → 미국 섹터 → 아카이브 → 데이터 품질 → 서비스 안내. Existing market/weekly/monthly/quality/accuracy/About paths remain exact. Content and publisher ordering/data/seal are read-only for this unit. Home card markup/data is u177; responsive data rendering and section jumps are u178; archive grouping is u179.

JS-off has a visible static `<noscript>` primary navigation with native links/details, because Material hides the drawer input and its label is not keyboard reachable without the adapter. Search Escape returns focus to its visible mobile trigger, or the visible header home link when the desktop input triggered the overlay; focusing the closed desktop search input would reopen it.

Escape focus candidates are checked for rendered visibility: originating trigger, header home link, then drawer trigger. This covers the960–1219px interval where Material hides both the search label and logo. Restoration occurs on the next animation frame after Material closes its overlay.1024px browser regression is required.
