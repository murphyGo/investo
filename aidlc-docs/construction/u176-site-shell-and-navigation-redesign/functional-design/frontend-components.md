# u176 Frontend components

MaterialHeader → existing logo/title, drawer/search/palette labels adapted to keyboard buttons; existing inputs remain the state owner. MaterialTabs/PrimaryDrawer → existing nav model with Korean labels. PageWrapper(home/article/reference) → unchanged Material content. SkipTarget → wrapper id=investo-content; fallback skip link when Material has no TOC-derived skip. CSS-onlyMarketGrid/Card contract is consumed by u177. No extra account/form/API.

HeaderControl accepts Enter/Space and native click; closes on Escape for search/drawer and returns focus. hidden opposite-palette labels have no rendered/tab stop. `data-testid=investo-header-{target}` and `investo-skip` remain stable. Static data/native controls are available without JS. No content clipping at200% text enlargement.

NoScriptNavigation: visible static native links plus details/summary for grouped archive/quality links, keyboard reachable before the offscreen drawer. JS-off Tab/Enter must reach watchlist/sectors. Search accessible name is explicitly `검색`, drawer `메뉴 열기`, palette uses existing names. Escape focus uses the visible trigger or header home fallback.

Escape focus candidates are checked for rendered visibility: originating trigger, header home link, then drawer trigger. This covers the960–1219px interval where Material hides both the search label and logo. Restoration occurs on the next animation frame after Material closes its overlay.1024px browser regression is required.

Mobile/tablet shortcuts: three native top-level links below the header at widths≤1219px, hidden on desktop. Material opens the active nested menu on quality/archive pages, so relying only on that drawer would exceed two menu actions. These shortcuts keep watchlist/sectors reachable in one link action from every page; the existing drawer retains full hierarchical navigation. Static links work with JS off and wrap at200% zoom instead of clipping.
