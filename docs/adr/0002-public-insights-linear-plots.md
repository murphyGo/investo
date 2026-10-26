# ADR 0002: Linear public-insights plots and native calendar

Date: 2026-10-26. Status: accepted for u184.

The calendar is a read-only view of at most128 validated events in30days. Native semantic month tables, local filters and an agenda cover its needs without a calendar dependency. Source-date precision and the published evaluation clock determine placement.

Use self-hosted MIT uPlot1.6.32 for public-insights numeric/time axes. Its linear x scale represents both elapsed observation days and Treasury maturities0.25/2/10/30years. Keep existing Lightweight Charts for briefing candlesticks. Package SHA512 and per-file SHA256/SRI are recorded beside the vendored package; JS+CSS total52,938bytes. No CDN, paid service, API or additional source call.

Visible axes, units, linear domains, exact source tables, source notices and keyboard inspection are mandatory. Missing observation days use null gaps. A single observation is labeled insufficient for trend inference. Static SVG/table fallbacks remain available if script loading fails. The loader and chart lifecycle must survive Material navigation, theme changes and responsive resizing.

Sources: [uPlot](https://github.com/leeoniya/uPlot), [data modes](https://leeoniya.github.io/uPlot/docs/data-modes.html), [Lightweight Charts time scale](https://tradingview.github.io/lightweight-charts/docs/time-scale).
