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

  function trendColor(bars) {
    if (bars.length < 2) return "#607d8b";
    return bars[bars.length - 1].close >= bars[0].close ? "#26a69a" : "#ef5350";
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

  function lineDataFromBars(bars) {
    var out = [];
    for (var i = 0; i < bars.length; i++) {
      out.push({ time: bars[i].time, value: bars[i].close });
    }
    return out;
  }

  function applySparklineTheme(chart, series, scheme, bars) {
    var theme = chartTheme(scheme);
    chart.applyOptions({
      layout: theme.layout,
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
    });
    series.applyOptions({ color: trendColor(bars) });
  }

  function renderSparkline(container, bars) {
    var scheme = currentColorScheme();
    var chart = window.LightweightCharts.createChart(container, {
      autoSize: true,
      height: 64,
      layout: chartTheme(scheme).layout,
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      crosshair: {
        vertLine: { visible: false, labelVisible: false },
        horzLine: { visible: false, labelVisible: false },
      },
      handleScroll: false,
      handleScale: false,
    });
    var series = chart.addLineSeries({
      color: trendColor(bars),
      lineWidth: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    series.setData(lineDataFromBars(bars));
    chart.timeScale().fitContent();
    return { chart: chart, series: series };
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

  function renderOne(div) {
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

    var ticker = div.getAttribute("data-ticker");
    var latestClose = readNumberAttr(div, "data-close");
    if (latestClose === null) latestClose = bars[bars.length - 1].close;
    var pct = readFiniteNumberAttr(div, "data-pct");
    var pctText = formatPct(pct);

    var details = document.createElement("details");
    details.className = "investo-chart-card";
    if (div.id) details.id = div.id;

    var summary = document.createElement("summary");
    summary.className = "investo-chart-summary";
    summary.setAttribute("aria-label", (ticker || "Ticker") + " chart details");

    var quote = document.createElement("span");
    quote.className = "investo-chart-quote";

    var tickerEl = document.createElement("strong");
    tickerEl.className = "investo-chart-ticker";
    tickerEl.textContent = ticker || "Ticker";
    quote.appendChild(tickerEl);

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

    var sparkline = document.createElement("span");
    sparkline.className = "investo-chart-sparkline";
    sparkline.setAttribute("aria-hidden", "true");
    summary.appendChild(sparkline);

    var expanded = document.createElement("div");
    expanded.className = "investo-chart-expanded";
    expanded.setAttribute("role", "img");
    expanded.setAttribute("aria-label", (ticker || "Ticker") + " candlestick chart");

    details.appendChild(summary);
    details.appendChild(expanded);
    div.replaceWith(details);

    var spark = null;
    var full = null;
    if (window.LightweightCharts) {
      spark = renderSparkline(sparkline, bars);
    } else {
      sparkline.style.display = "none";
    }

    details.addEventListener("toggle", function () {
      if (!details.open || !window.LightweightCharts) return;
      if (full === null) {
        full = renderCandlestick(expanded, div, bars);
      }
      window.requestAnimationFrame(function () {
        full.chart.timeScale().fitContent();
      });
    });

    // Live theme switching — observe mkdocs-material's light/dark
    // scheme attribute on <html> and re-apply layout colors. The
    // observer is disconnected when the div leaves the DOM (single-
    // page nav not used here, so the page reload covers cleanup).
    var observer = new MutationObserver(function () {
      var scheme = currentColorScheme();
      if (spark !== null) {
        applySparklineTheme(spark.chart, spark.series, scheme, bars);
      }
      if (full !== null) {
        applyCandlestickTheme(full.chart, full.series, scheme);
      }
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
