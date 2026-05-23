/*
 * investo-chart-init.js — u50 lightweight-charts-embed
 *
 * Progressive-enhancement layer for the daily briefing pages. Scans
 * the rendered DOM for ``<div class="investo-chart" ...>`` placeholders
 * (emitted by ``investo.publisher.charts.render_chart_placeholder``)
 * and turns each one into a compact ticker/price card with a small
 * line chart. Clicking the card opens the full candlestick chart with
 * an ATH dashed line and 52-week range price-lines.
 *
 * The static SVG cards rendered by ``investo.visuals`` (u24 / u26)
 * remain in place and serve as the no-JS fallback (Telegram message
 * unfurls, mail clients, RSS readers, accessibility tools).
 *
 * Project rule reminders:
 *   - No external CDN; the page loads
 *     ``assets/lightweight-charts.standalone.production.js`` from the
 *     repo (see ``mkdocs.yml`` ``extra_javascript``).
 *   - No secrets / tokens inline.
 *   - u75: heavy OHLC history is no longer embedded inline. The compact
 *     card renders from the small summary ``data-*`` attributes alone;
 *     the full candlestick history is fetched from the archive-local
 *     sidecar JSON referenced by ``data-history-src`` only when the
 *     reader expands the card (no viewport prefetch in v1). A failed
 *     fetch degrades that one card without breaking the others. The
 *     fetch is a same-origin static file on GitHub Pages — no CDN, no
 *     server endpoint, no secret.
 */

(function () {
  "use strict";

  // Hard cap so a future regression that floods the page with chart
  // placeholders cannot blow the browser memory budget. Aligned with
  // u50 plan §Open questions (page-bundle size budget).
  var MAX_CHARTS_PER_PAGE = 5;

  function isPositiveNumber(value) {
    return typeof value === "number" && isFinite(value) && value > 0;
  }

  function isFiniteNumber(value) {
    return typeof value === "number" && isFinite(value);
  }

  function rowToBar(row) {
    if (!row || typeof row !== "object") return null;
    var t = row.t;
    var o = parseFloat(row.o);
    var h = parseFloat(row.h);
    var l = parseFloat(row.l);
    var c = parseFloat(row.c);
    if (
      typeof t !== "string" ||
      !isPositiveNumber(o) ||
      !isPositiveNumber(h) ||
      !isPositiveNumber(l) ||
      !isPositiveNumber(c)
    ) {
      return null;
    }
    return { time: t, open: o, high: h, low: l, close: c };
  }

  function readNumberAttr(div, name) {
    var raw = div.getAttribute(name);
    if (raw === null || raw === "") return null;
    var n = parseFloat(raw);
    return isPositiveNumber(n) ? n : null;
  }

  function readFiniteNumberAttr(div, name) {
    var raw = div.getAttribute(name);
    if (raw === null || raw === "") return null;
    var n = parseFloat(raw);
    return isFiniteNumber(n) ? n : null;
  }

  function currentColorScheme() {
    var attr =
      document.documentElement.getAttribute("data-md-color-scheme") || "default";
    return attr === "slate" ? "dark" : "light";
  }

  function chartTheme(scheme) {
    if (scheme === "dark") {
      return {
        layout: {
          background: { color: "transparent" },
          textColor: "#d0d0d0",
        },
        grid: {
          vertLines: { color: "#2a2a2a" },
          horzLines: { color: "#2a2a2a" },
        },
        upColor: "#26a69a",
        downColor: "#ef5350",
      };
    }
    return {
      layout: {
        background: { color: "transparent" },
        textColor: "#212121",
      },
      grid: {
        vertLines: { color: "#eeeeee" },
        horzLines: { color: "#eeeeee" },
      },
      upColor: "#26a69a",
      downColor: "#ef5350",
    };
  }

  function applyCandlestickTheme(chart, series, scheme) {
    var theme = chartTheme(scheme);
    chart.applyOptions({
      layout: theme.layout,
      grid: theme.grid,
    });
    series.applyOptions({
      upColor: theme.upColor,
      downColor: theme.downColor,
      borderUpColor: theme.upColor,
      borderDownColor: theme.downColor,
      wickUpColor: theme.upColor,
      wickDownColor: theme.downColor,
    });
  }

  function formatPrice(value) {
    if (!isPositiveNumber(value)) return "n/a";
    var abs = Math.abs(value);
    var digits = abs >= 1000 ? 0 : abs >= 100 ? 1 : abs >= 1 ? 2 : 4;
    return value.toLocaleString(undefined, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function formatPct(value) {
    if (!isFiniteNumber(value)) return "";
    var sign = value > 0 ? "+" : "";
    return sign + value.toFixed(2) + "%";
  }

  function renderCandlestick(container, sourceDiv, bars) {
    var scheme = currentColorScheme();
    var theme = chartTheme(scheme);

    var chart = window.LightweightCharts.createChart(container, {
      autoSize: true,
      layout: theme.layout,
      grid: theme.grid,
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true },
      handleScroll: true,
      handleScale: true,
    });

    var series = chart.addCandlestickSeries({
      upColor: theme.upColor,
      downColor: theme.downColor,
      borderUpColor: theme.upColor,
      borderDownColor: theme.downColor,
      wickUpColor: theme.upColor,
      wickDownColor: theme.downColor,
    });
    series.setData(bars);

    var ath = readNumberAttr(sourceDiv, "data-ath");
    var w52High = readNumberAttr(sourceDiv, "data-52w-high");
    var w52Low = readNumberAttr(sourceDiv, "data-52w-low");

    if (ath !== null) {
      series.createPriceLine({
        price: ath,
        color: "#ff9800",
        lineWidth: 1,
        lineStyle: window.LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: "ATH",
      });
    }
    if (w52High !== null && w52High !== ath) {
      series.createPriceLine({
        price: w52High,
        color: "#90a4ae",
        lineWidth: 1,
        lineStyle: window.LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: "52w high",
      });
    }
    if (w52Low !== null) {
      series.createPriceLine({
        price: w52Low,
        color: "#90a4ae",
        lineWidth: 1,
        lineStyle: window.LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: "52w low",
      });
    }

    chart.timeScale().fitContent();
    return { chart: chart, series: series };
  }

  function barsFromHistory(history) {
    if (!Array.isArray(history) || history.length === 0) return [];
    var bars = [];
    for (var i = 0; i < history.length; i++) {
      var bar = rowToBar(history[i]);
      if (bar !== null) bars.push(bar);
    }
    return bars;
  }

  // u75 — fetch the externalised sidecar JSON and hand back the parsed
  // bar list. Resolves to [] on any failure so the caller can show a
  // per-card error state without touching sibling cards. The sidecar is
  // a same-origin static file; ``fetch`` is feature-detected so older
  // browsers fall back to "no chart" rather than throwing.
  function loadSidecarBars(src) {
    if (!src || typeof fetch !== "function") {
      return Promise.resolve([]);
    }
    return fetch(src, { credentials: "same-origin" })
      .then(function (resp) {
        if (!resp || !resp.ok) return null;
        return resp.json();
      })
      .then(function (payload) {
        if (!payload || typeof payload !== "object") return [];
        return barsFromHistory(payload.history);
      })
      .catch(function (err) {
        if (typeof console !== "undefined" && console.warn) {
          console.warn("[investo-chart] sidecar fetch failed:", src, err);
        }
        return [];
      });
  }

  function renderOne(div) {
    var historySrc = div.getAttribute("data-history-src");
    if (!historySrc) {
      // No externalised history reference — nothing to expand into.
      div.style.display = "none";
      return false;
    }

    var ticker = div.getAttribute("data-ticker");
    // u70 — canonical reader label from the shared anchor-label registry
    // (e.g. ^IXIC -> "나스닥 종합", never "Nasdaq 100"). Falls back to the
    // raw ticker when the attribute is absent (older archives).
    var label = div.getAttribute("data-label");
    var latestClose = readNumberAttr(div, "data-close");
    var pct = readFiniteNumberAttr(div, "data-pct");
    var pctText = formatPct(pct);

    var details = document.createElement("details");
    details.className = "investo-chart-card";
    if (div.id) details.id = div.id;

    var summary = document.createElement("summary");
    summary.className = "investo-chart-summary";
    summary.setAttribute("aria-label", (label || ticker || "Ticker") + " chart details");

    var quote = document.createElement("span");
    quote.className = "investo-chart-quote";

    var tickerEl = document.createElement("strong");
    tickerEl.className = "investo-chart-ticker";
    tickerEl.textContent = ticker || "Ticker";
    if (label && label !== ticker) tickerEl.title = label;
    quote.appendChild(tickerEl);

    if (label && label !== ticker) {
      var labelEl = document.createElement("span");
      labelEl.className = "investo-chart-label";
      labelEl.textContent = label;
      quote.appendChild(labelEl);
    }

    var priceEl = document.createElement("span");
    priceEl.className = "investo-chart-price";
    priceEl.textContent = formatPrice(latestClose);
    quote.appendChild(priceEl);

    if (pctText) {
      var pctEl = document.createElement("span");
      pctEl.className = pct >= 0 ? "investo-chart-pct is-up" : "investo-chart-pct is-down";
      pctEl.textContent = pctText;
      quote.appendChild(pctEl);
    }
    summary.appendChild(quote);

    // u75 — the expand area starts empty. The sparkline + candlestick
    // are rendered lazily from the sidecar JSON the first time the card
    // is opened, so the compact card costs zero history bytes up front.
    var expanded = document.createElement("div");
    expanded.className = "investo-chart-expanded";
    expanded.setAttribute("role", "img");
    expanded.setAttribute("aria-label", (ticker || "Ticker") + " candlestick chart");

    details.appendChild(summary);
    details.appendChild(expanded);
    div.replaceWith(details);

    // Per-card lazy-load state. ``loadState`` advances idle -> loading
    // -> (ready | error); only one fetch is ever issued per card.
    var loadState = "idle";
    var bars = [];
    var full = null;

    function setMessage(text) {
      expanded.textContent = "";
      var msg = document.createElement("p");
      msg.className = "investo-chart-message";
      msg.textContent = text;
      expanded.appendChild(msg);
    }

    function renderExpanded() {
      if (!window.LightweightCharts || bars.length === 0) {
        setMessage("차트 데이터를 불러오지 못했습니다.");
        return;
      }
      expanded.textContent = "";
      full = renderCandlestick(expanded, div, bars);
      window.requestAnimationFrame(function () {
        full.chart.timeScale().fitContent();
      });
    }

    // Live theme switching — observe mkdocs-material's light/dark
    // scheme attribute on <html> and re-apply layout colors. The
    // observer is disconnected when the div leaves the DOM (single-
    // page nav not used here, so the page reload covers cleanup).
    var observer = new MutationObserver(function () {
      if (full !== null) {
        applyCandlestickTheme(full.chart, full.series, currentColorScheme());
      }
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-md-color-scheme"],
    });

    details.addEventListener("toggle", function () {
      if (!details.open) return;
      if (loadState === "ready") {
        if (full === null) renderExpanded();
        else {
          window.requestAnimationFrame(function () {
            full.chart.timeScale().fitContent();
          });
        }
        return;
      }
      if (loadState !== "idle") return;
      loadState = "loading";
      setMessage("차트를 불러오는 중…");
      loadSidecarBars(historySrc).then(function (loadedBars) {
        bars = loadedBars;
        loadState = loadedBars.length > 0 ? "ready" : "error";
        if (loadState === "error") {
          setMessage("차트 데이터를 불러오지 못했습니다.");
          return;
        }
        renderExpanded();
      });
    });

    return true;
  }

  function init() {
    if (!document || !document.querySelectorAll) return;
    var divs = document.querySelectorAll(".investo-chart");
    var rendered = 0;
    for (var i = 0; i < divs.length && i < MAX_CHARTS_PER_PAGE; i++) {
      if (renderOne(divs[i])) rendered++;
    }
    if (typeof console !== "undefined" && console.log) {
      console.log("[investo-chart] initialised:", rendered, "of", divs.length);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
