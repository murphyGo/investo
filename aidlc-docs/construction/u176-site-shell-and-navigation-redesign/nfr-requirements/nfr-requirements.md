# u176 Focused NFR requirements

NFR002/003/004/005/006 and R13 retained. Four 390×844/1440×1000×default/slate combinations cover home/article/watchlist/sectors/quality; document horizontal overflow0, tables remain local scroll containers.200% text enlargement and JS-off retain content/navigation. Ordinary text4.5:1, focus3:1, primary controls44×44px. Keyboard Tab/Enter/Space/Escape, drawer, search results, palette persistence, skip focus and current navigation required. OG/Twitter and Material SVG fragments preserved.

Payload: one CSS≤16KiB, optional local keyboard adapter≤4KiB; no package/font/CDN/API beyond existing site requests. No publisher/runtime/seal/asset manifest changes. Browser evidence records actual style/DOM/interaction, not the earlier standalone concept. Strict build and existing Material guard are required. Responsive layout fallback preserves every static link.
