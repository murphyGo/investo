# u187 focused functional and NFR design

## Reader experience

The major-events page opens on a real month grid and a date agenda. The month grid covers only the existing validated30-day window, including adjacent months when needed. Month controls cannot imply knowledge outside that window. The default range becomes30days so the month view is useful;7days remains a filter. A selected date narrows the agenda and has a clear reset. Category colors always have text labels. Desktop cells show short event previews; mobile cells show compact date/count previews and retain readable detail below. The calendar may scroll inside its named region at extreme zoom, never widen the whole page.

Exact instants stay on their verified KST date. Date-only events stay on the source US Eastern date with “미 동부 · 시간 미정”; they are never relabeled all-day KST. Both types have explicit badges in cells and full dates in the agenda. Verified multi-day periods occupy every included local date, clipped to the published window. “게시 기준일” is the module's evaluated clock, not an invented live browser clock. A blank cell means no selected published event, not complete market coverage. Navigation and filtering are local DOM operations; no network or calendar service.

## Charts

uPlot1.6.32 is pinned from the official npm package, with SHA512 package integrity, per-file SHA256, MIT notice and same-origin vendoring. It supports linear time and numeric scales. The existing Lightweight Charts financial-bar axis is retained for briefing candlesticks; using its indexed spacing for this numeric maturity plot would misstate distance. No paid package/CDN/runtime API is introduced. New vendor JS+CSS must stay under80KiB uncompressed and loads only when an insights chart is needed.

The Treasury curve uses x=0.25/2/10/30years and y=published percent. A visible caption names both axes, linear scaling and the shown y-domain, including when the y-axis does not start at zero. Four actual points and their source date remain visible in an exact table. The connecting line describes those observations, not a fitted or inferred complete yield curve. Incomplete or mixed-date inputs preserve the existing limited state instead of manufacturing a curve.

History remains same-definition, hash-verified, recent30actual observations. x uses elapsed calendar-day distances, with UTC date arithmetic solely for plotting an existing date label (not timezone conversion of a source date). Missing calendar dates break the line; no missing values are invented. A single real observation can be inspected but is labeled insufficient for change/trend inference. FNG has a fixed0–100 index axis; other domains have padded linear bounds stated in readable text. Fraction values can be displayed as percent with explicit conversion while the exact original-value table remains available. Negative and constant values must have finite, legible domains. No logarithmic or dual-unit axes, smoothing, arbitrary normalization or mixed-provider history.

Every interactive chart has visible units/date basis/domain, pointer readout and a keyboard-accessible observation selector. Source-required attribution remains visible with each graph and in existing tables. Script/vendor/network failure leaves exact data and honest status readable. Responsive resizing and Material instant navigation destroy detached charts/listeners/observers; theme changes update colors. Tests verify real coordinates/scales rather than only the existence of a canvas.

## Acceptance boundaries

AC187.1 Month/day navigation, category/range filters and no-JS list preserve all event identities and precision through year/month/DST boundaries.
AC187.2 Calendar does not invent all-day status, KST timestamps, result/importance or out-of-window coverage; labels escape untrusted text.
AC187.3 Maturity0.25/2/10/30 and irregular history dates have proportional x distances; units, y-domain and linear scale are readable.
AC187.4 Empty/one-point/flat/negative/gapped/revised histories and fraction display preserve exact source tables and no imputation.
AC187.5 Hash mismatch, CDN absence, vendor failure, no-JS, theme, resize and repeat navigation degrade safely with bounded resources.
AC187.6 Mobile390x844/desktop1440x900, two schemes, JS on/off and200% equivalent zoom pass page containment and accessible controls; actual production data remains labeled as actual, synthetic stress fixtures as synthetic.
AC187.7 Current/history bytes, snapshot identities, evaluated/source clocks and qualification permissions remain unchanged; manifest index_hash values are recomputed and validate_bundle must pass by presentation refresh; no source/LLM/Telegram calls or scheduled acceptance increments.
