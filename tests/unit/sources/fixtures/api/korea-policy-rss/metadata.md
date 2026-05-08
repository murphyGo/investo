# korea-policy-rss fixture metadata

- Source: Financial Services Commission RSS service.
- Official RSS service page: https://www.fsc.go.kr/ut060101
- Default feed represented: `http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111`
- Captured timestamp: synthetic recorded-shape fixture for 2026-05-08 development; not live production data.
- HTTP status represented: 200 OK for RSS 2.0 XML responses.
- Fair access notes: adapter uses the shared `retry_get` helper with bounded timeout/retry and response-size enforcement.
