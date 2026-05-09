/*
 * investo-chart-init.js — u50 lightweight-charts-embed
 *
 * Progressive-enhancement layer for the daily briefing pages. Scans
 * the rendered DOM for ``<div class="investo-chart" ...>`` placeholders
 * (emitted by ``investo.publisher.charts.render_chart_placeholder``)
 * and turns each one into an interactive Lightweight Charts candlestick
 * chart with an ATH dashed line and 52-week range price-lines.
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
 *   - All chart data arrives via ``data-*`` attributes the publisher
 *     already redacts; this script does no fetching of its own.
 */

(function () {
  "use strict";

  // Hard cap so a future regression that floods the page with chart
  // placeholders cannot blow the browser memory budget. Aligned with
  // u50 plan §Open questions (page-bundle size budget).
  var MAX_CHARTS_PER_PAGE = 5;

  function safeParse(json) {
    if (!json) return null;
    try {
      return JSON.parse(json);
    } catch (err) {
      // Quiet warn — the SVG fallback already covers the visual surface.
      if (typeof console !== "undefined" && console.warn) {
        console.warn("[investo-chart] data-history JSON parse failed:", err);
      }
      return null;
    }
  }

  function isPositiveNumber(value) {
    return typeof value === "number" && isFinite(value) && value > 0;
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

  function currentColorScheme() {
    var attr =
      document.documentElement.getAttribute("data-md-color-scheme") || "default";
    return attr === "slate" ? "dark" : "light";
  }

  function chartTheme(scheme) {
    if (scheme === "dark") {
      return {
        layout: {
          background: { color: "#1e1e1e" },
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
        background: { color: "#ffffff" },
        textColor: "#212121" ,
      },
      grid: {
        vertLines: { color: "#eeeeee" },
        horzLines: { color: "#eeeeee" },
      },
      upColor: "#26a69a",
      downColor: "#ef5350",
    };
  }

  function applyTheme(chart, series, scheme) {
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

  function renderOne(div) {
    if (!window.LightweightCharts) {
      // The bundle did not load; SVG fallback covers the surface.
      return false;
    }

    var history = safeParse(div.getAttribute("data-history"));
    if (!Array.isArray(history) || history.length === 0) {
      div.style.display = "none";
      return false;
    }

    var bars = [];
    for (var i = 0; i < history.length; i++) {
      var bar = rowToBar(history[i]);
      if (bar !== null) bars.push(bar);
    }
    if (bars.length === 0) {
      div.style.display = "none";
      return false;
    }

    // Reserve a viewable surface; the placeholder is sized via CSS but
    // we set a minimum height so collapsed flex parents do not zero
    // out the chart canvas.
    if (!div.style.height) div.style.height = "320px";
    div.style.minHeight = "240px";

    // Aria label from data-ticker so screen readers announce the chart
    // surface meaningfully ("BTC-USD chart") instead of bare "div".
    var ticker = div.getAttribute("data-ticker");
    if (ticker && !div.getAttribute("aria-label")) {
      div.setAttribute("role", "img");
      div.setAttribute("aria-label", ticker + " chart");
    }

    var scheme = currentColorScheme();
    var theme = chartTheme(scheme);

    var chart = window.LightweightCharts.createChart(div, {
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

    var ath = readNumberAttr(div, "data-ath");
    var w52High = readNumberAttr(div, "data-52w-high");
    var w52Low = readNumberAttr(div, "data-52w-low");

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

    // Live theme switching — observe mkdocs-material's light/dark
    // scheme attribute on <html> and re-apply layout colors. The
    // observer is disconnected when the div leaves the DOM (single-
    // page nav not used here, so the page reload covers cleanup).
    var observer = new MutationObserver(function () {
      applyTheme(chart, series, currentColorScheme());
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-md-color-scheme"],
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
