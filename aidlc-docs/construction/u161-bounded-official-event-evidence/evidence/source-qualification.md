# u161 source qualification evidence

Checked: 2026-09-26 18:18:21 UTC (2026-09-27 KST). Baseline: u160 `79b9f03981a2f26ef74126e4bb86928a9b118950`. Qualification is a bounded source/parser decision for development, not scheduled-run recovery, universal completeness or production activation.

Public machine-readable contract: [ops/event_source_qualification.json](../../../../ops/event_source_qualification.json). There are three qualified body families and one blocked family. HTTP success alone was not used as qualification.

## Method and private evidence boundary

Public unauthenticated GET probes used curl 8.7.1 with its declared default user agent, `Accept: */*`, compressed-response negotiation, five-second connect timeout, fifteen-second total timeout, no retries and no automatic redirect following. Feed probes were bounded at one MiB and body probes at 500 KiB. The FSC HTTP redirect target was requested separately after confirming the same provider/host/path. No browser impersonation, cookies, paid service, credential, proxy bypass or alternate provider was used.

Decoded response bodies and full headers are retained only in the ignored worktree `.tmp/u161-qualification/` directory. They are not public fixtures. `git check-ignore` confirmed that the raw-body paths are ignored. Public evidence below contains request URLs, bounded status/header/parser facts, byte counts and SHA-256 values; no full body or secret is published. Hashes are over the decoded bytes written by curl, not compressed transfer bytes. A local standard-library HTML parser inspected extraction boundaries without executing scripts.

## Existing failed feed diagnostics

| Source | Current endpoint and response | Parser evidence | Decision |
| --- | --- | --- | --- |
| `cnbc-top-news` | [Existing US top-news RSS](https://www.cnbc.com/id/100003114/device/rss/rss.html): HTTP 403, `text/html`, no redirect; 418 decoded bytes | Access-denial HTML is not a usable RSS document; XML parse fails. [CNBC's own RSS discovery path](https://www.cnbc.com/rss-feeds/) also returned 403, so current official replacement instructions could not be verified. | **Blocked**, unchanged provider/source identity. No access workaround or alternate media substitution. A successful historical fixture is not evidence of current recovery. |
| `korea-policy-rss` | [FSC official RSS guide](https://www.fsc.go.kr/ut060101): HTTP 200 and still lists the legacy HTTP feed. `http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111` returns 302 with `Location: https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111`. The [same-provider HTTPS feed](https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111) returns HTTP 200, `text/xml;charset=UTF-8`, 263,422 decoded bytes, ten RSS items. | All ten rows lack `pubDate` and contain `{http://purl.org/dc/elements/1.1/}date`, for example `2026-09-23 00:00:00` without a timezone. Current normalization accepted **0/10**. Replaying the captured 302 body through the pre-repair `_fetch_feed` produced `SourceFetchError: malformed XML`; replaying HTTPS 200 through that parser produced zero items for the matching 2026-09-23 KST date. | **Same-provider repair supported**: use the exact HTTPS redirect target and add a bounded `dc:date` fallback with date precision. No exact occurrence time can be claimed from the naive midnight value. Parent owns implementation and post-repair validation; no production recovery is asserted here. |

The shared legacy retry helper returns responses below HTTP 400, and the default client does not follow redirects; consequently the FSC 302 HTML reaches XML parsing. The HTTPS response then exposes a second, independent date-schema mismatch. The source name, category, tier and routing must remain unchanged.

FSC regression shape: synthetic RSS with a `dc:date` value in the observed format, no `pubDate`, valid original-provider link and HTML description; the first of duplicate `description` fields is sufficient. Assert a date-only item and local-day overlap instead of assigning midnight as a known event instant. Invalid date must remain excluded. The captured same-provider response is available privately for an additional read-only parser replay.

Post-repair validation at **2026-09-26 18:25:37 UTC**: the parent's scoped HTTPS/date-fallback adapter accepted **7 items** from the recorded feed for the 2026-09-23 KST window, all with date precision and no fabricated `event_time_basis`. One additional actual `_fetch_feed` call to the default HTTPS endpoint, under an eight-second outer timeout, returned HTTP 200 `text/xml;charset=UTF-8`, no redirect and the same seven date-only items. The original ten-row feed contains seven dates on September 23, one on September 22 and two on September 21, so three rows were correctly outside this window. This verifies the local same-provider transport/parser repair; it does not establish recovery in scheduled production.

Diagnostic hashes:

| Artifact | SHA-256 |
| --- | --- |
| CNBC RSS 403 body | `b4358d4e9178dadfe67447a4ece3d161add1553cf49852e229c236d57afc97fb` |
| FSC HTTP 302 body | `80f5e0c00e7735001a1615add7df5363fa6e8d70820c392d5aa3eb7f81cb9f4a` |
| FSC HTTPS RSS body | `1d1f2e3647c36b46863f1a30e43a7c7cb0edf238ee2060a9973cd774655f3dc3` |

## Official body qualification matrix

| Source | Official discovery and directly linked test body | Live evidence | Status and allowed scope |
| --- | --- | --- | --- |
| `fomc-rss` | [Fed RSS guide](https://www.federalreserve.gov/feeds/feeds.htm) links the configured [press feed](https://www.federalreserve.gov/feeds/press_all.xml); its parsed 20 items directly include [the tested monetary-policy release](https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm). | Feed 200 `text/xml`; body 200 `text/html`, zero redirects, 82,636 decoded bytes, one selected body, 963 text characters. | **Qualified**: exact host `www.federalreserve.gov`, path prefix `/newsevents/pressreleases/`, HTML Board-authored announcement text only. |
| `fed-speech-rss` | [Fed RSS guide](https://www.federalreserve.gov/feeds/feeds.htm) links the configured [speech feed](https://www.federalreserve.gov/feeds/speeches.xml); its parsed 15 items directly include [the tested Board speech](https://www.federalreserve.gov/newsevents/speech/barr20260923a.htm). | Feed 200 `text/xml`; body 200 `text/html`, zero redirects, 113,366 decoded bytes, one selected body, 25,324 text characters before the 1,200-character excerpt cap. | **Qualified**: exact host `www.federalreserve.gov`, prefix `/newsevents/speech/`. The adapter's testimony feed may still supply feed evidence, but testimony body paths are not qualified by this record. |
| `sec-newsroom-rss` | [SEC official RSS guide](https://www.sec.gov/about/rss-feeds) identifies the configured [press feed](https://www.sec.gov/news/pressreleases.rss), which parsed 25 items and directly linked [the tested newsroom release](https://www.sec.gov/newsroom/press-releases/2026-93-sec-publishes-updated-market-statistics-highlighting-increase-ipos-proceeds-raised). | Feed 200 `application/rss+xml; charset=utf-8`; direct body 403 `text/html`. The official discovery page was visible through web browsing, while the local curl request returned 403. | **Blocked** for new body HTTP. No parser/rights/body qualification inferred from the accessible feed or crawler view; no alternate user-agent attempt or access workaround. |
| `cftc-policy-rss` | [CFTC official RSS guide](https://www.cftc.gov/RSS/index.htm) links the configured [general release feed](https://www.cftc.gov/RSS/RSSGP/rssgp.xml); its parsed ten items directly include [release 9303-26](https://www.cftc.gov/PressRoom/PressReleases/9303-26). | Feed 200 `application/rss+xml; charset=utf-8`; body 200 `text/html; charset=utf-8`, zero redirects, 35,425 decoded bytes, one selected body, 1,126 text characters. | **Qualified**: exact host `www.cftc.gov`, prefix `/PressRoom/PressReleases/`. Speech/testimony, attachment and document-download paths are excluded. |

The [Federal Reserve's copyright/trademark notice](https://www.federalreserve.gov/disclaimer.htm) permits copying Board website information by default with attribution, while excluding independently protected third-party material and official seals/logos. The [CFTC copyright policy](https://www.cftc.gov/WebPolicy/index.htm) likewise identifies government information as public domain and requests acknowledgement, while distinguishing privately contributed/licensed material. Qualification covers the agencies' own release/speech text, not imagery, external cited works, attachments or blanket reuse of everything on either domain. SEC Facebook terms were not treated as permission for SEC website bodies.

## Versioned extraction contract

| Selector ID | Exact structural scope | Live shape result |
| --- | --- | --- |
| `fed-article-body-v1` | `#article > div.col-xs-12.col-sm-8.col-md-8:not(.heading)`: the direct article-body column, excluding the sibling heading/share controls. | Exactly one target in both tested Fed bodies. Nonempty plain text; no navigation/footer text. |
| `cftc-press-article-body-v1` | `article .field--name-body`: a body field inside the release article. | Exactly one target. A global `.field--name-body` selector is unsafe because the same class also appears in header/footer blocks. |

Extraction must require the qualified selector version and a unique nonempty region; remove script/style/noscript content, normalize whitespace, cap the excerpt at 1,200 characters, and retain the original source identity/URL. Missing or duplicate regions fail to enrichment-unavailable, preserving the feed item. The manifest's path prefix is only one restriction: the URL must also be the same item's directly supplied official link, HTTPS, without credentials/query/path escapes or private/local destinations. Runtime request, concurrency, decoded-size, redirect and total deadlines remain those of u161 and are not relaxed by qualification.

| Live decoded body | Fixture SHA-256 | Local 1,200-character-or-shorter extracted text SHA-256 |
| --- | --- | --- |
| FOMC release | `9dfe2c992f5f45592376a155a9406239e19e44a051eef56eb850073ccd6a7a4c` | `1dbc7d2dc0101e203c287be50b0cf137ffe375c36562620bc5ded4cbe274551b` |
| Fed speech | `ae93cb877b662d743449dcf79c0a8cddeb0f985f6f08320474948f301b164eba` | `98a85071dfb5f7b6303c2396e9f5db8712c0bd1d540f1a63a4d8cdcd7e9bc77f` |
| CFTC release | `d4a5f89c3837693b00c54894ebad18f9a555a3cae40125cb348d7ba49a289891` | `2fc2b6701695da9ea8166c2fe72e215d0f2731acb15e64ac6ad3403694c944f4` |

The extracted-text hashes describe this inspection parser, not a new independently authoritative source. Production extraction must be tested against the same private live bytes; synthetic public fixtures should mirror structure without copying raw agency pages. Production code may normalize paragraph boundaries differently while preserving the correct region and budget.

Implementation parity check: the actual `sources.event_evidence._body_excerpt` function was subsequently run against the manifest records and all three private live bodies. It returned no failure reason, lengths 963/1,200/1,126 respectively, and exactly the same three excerpt hashes recorded above. No additional HTTP was required for this check.

## Handoff and limits

Positive body qualification was supplied to the helper owner before Stage C implementation began. No new source registration, provider substitution, commercial body fetch or production activation occurred. CNBC remains blocked. FSC's separately owned transport/schema repair has the local captured/live evidence above. SEC body access remains blocked. The three qualified families do not imply all endpoints or all historical variants are qualified. Scheduled runtime, notification, publishing and DEBT-090 performance closure are not established by these probes.
