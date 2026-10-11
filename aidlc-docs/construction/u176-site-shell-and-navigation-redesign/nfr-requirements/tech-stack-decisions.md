# u176 Tech stack decisions

Use pinned MkDocs Material and existing native search/drawer/palette. One template content/header override preserves super() and OG block. `investo-ui.css` defines tokens and scoped :has layout. A small self-hosted `investo-navigation.js` provides label keyboard semantics/Escape focus; no new package or external service. Separate NFR Design SKIP: all decisions, resource bounds, failure/no-JS paths and exact component ownership are specified here; no infrastructure/data boundary is introduced. Infrastructure SKIP: existing Pages deployment.

Built-page contract test asserts only root gets home scope and existing OG/search/navigation survive, not copied CSS numeric values. Actual browser measures widths/contrast/focus/target sizes and interaction. CSS/keyboard failures leave static content/native navigation; all Python producer/state/trust tests remain unchanged.
