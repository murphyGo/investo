# Code Summary: u16 public-site-discovery

**Date**: 2026-05-07

## Completed

- Updated the public Home page to describe domestic, US, and crypto segmented briefings.
- Added direct links to the latest archived domestic, US, and crypto briefings.
- Updated About with the current integrated source categories and known coverage limits.
- Updated Archive landing copy to describe segmented paths and keep the legacy single-briefing path discoverable.
- Chose the smallest latest-link strategy for this slice: static links to the latest committed archive bundle, with no new publisher code.

## Files Changed

- `site_docs/index.md`
- `site_docs/about.md`
- `archive/index.md`

## Verification

- `uv run mkdocs build --strict`
