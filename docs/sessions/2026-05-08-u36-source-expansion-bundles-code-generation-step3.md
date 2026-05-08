# 2026-05-08 u36 source expansion bundles — step 3

## Context

Complete the domestic base layer with an official policy/news RSS source that does not rely on Naver Finance, unofficial finance pages, or KRX/KIND scraping.

## Source

Financial Services Commission RSS service page: https://www.fsc.go.kr/ut060101

Default feed: `http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111`

## Implementation

- Added `src/investo/sources/korea_policy_rss.py`.
- Registered `korea-policy-rss` in source discovery and plugin-contract tests.
- Added the source to domestic segment routing.
- Added fixture tests for FSC RSS parsing, HTML stripping, strict target-date filtering, dedupe/sort, partial feed failure, all-feed failure, and unsupported URL schemes.

## Verification

```bash
uv run pytest tests/unit/sources/test_korea_policy_rss.py tests/unit/sources/test_plugin_contract.py tests/unit/briefing/test_segments.py -q
```

Result: 26 passed.
