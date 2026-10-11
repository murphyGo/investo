# u176 Business rules

D176.1: Korean primary nav order as in the logic model; watchlist/index.md is a top-level link, sectors/index.md retained. One native mobile drawer plus mobile/tablet shortcuts for 최신 시황/관심 자산/미국 섹터. Shortcuts are display:none on desktop; no hidden duplicate tab stops.
D176.2: Desktop tabs and mobile Material drawer retain search, palette, OS default and persisted preference. Watchlist/sectors each require at most drawer-open + link-click.
D176.3: Main grid1280px, home content1120px, article max76ch; home desktop sidebar removal at1220px, mobile drawer retained. Card grid3columns at980px and above, otherwise1column. No page-wide overflow hiding.
D176.4: Light bg#f4f7f8/surface#fff/ink#153237/muted#53666b/accent#006d68; slate bg#101b20/surface#17262c/ink#e8f2f2/muted#a9bbc0/accent#81d9cc. Header#153237/#17262c with white text. Decorative borders do not imply status. Body16px/line-height1.75, secondary14px, actions44px.
D176.5: `investo-page-home/article/reference` is template metadata scope; `investo-home`, `investo-home-quick-links`, `investo-market-grid/card/status/date/link` are u177 consumer classes. Schema-specific headings are never page-type detectors. CSS :has scope has a safe narrower-layout fallback in older browsers; static links/data remain accessible.

No category badge, data quality, date, event, source or activation is inferred in CSS/JS. Future v3 remains u169/u171 semantics.
