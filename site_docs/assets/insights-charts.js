/* u184: same-origin uPlot enhancement; exact tables and static curve survive failure. */
(() => {
  'use strict';
  const DAY = 86400000;
  const UNITS = {percent: '%', basis_point: 'bp', krw_per_usd: '원/USD', index: '지수', usd: 'USD', usd_notional: 'USD 명목', fraction: '%'};
  function dateValue(iso) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) throw new Error('date');
    const value = Date.parse(iso + 'T00:00:00Z');
    if (!Number.isFinite(value) || new Date(value).toISOString().slice(0, 10) !== iso) throw new Error('date');
    return value;
  }
  function domain(values, fixed) {
    if (!values.length || values.some(v => !Number.isFinite(v))) throw new Error('value');
    const low = Math.min(...values), high = Math.max(...values);
    if (fixed) {
      if (low < fixed[0] || high > fixed[1]) throw new Error('domain');
      return fixed;
    }
    const padding = low === high ? Math.max(Math.abs(low) * .05, low === 0 ? 1 : 1e-9) : (high - low) * .12;
    const rough = (high - low + 2 * padding) / 4;
    const magnitude = 10 ** Math.floor(Math.log10(rough));
    const step = [1, 2, 2.5, 5, 10].find(n => n * magnitude >= rough) * magnitude;
    const range = [Math.floor((low - padding) / step) * step, Math.ceil((high + padding) / step) * step].map(v => Number(v.toPrecision(12)));
    if (!range.every(Number.isFinite) || range[0] >= range[1] || range[0] > low || range[1] < high) throw new Error('domain');
    return range;
  }
  function historyData(rows, unit) {
    if (!rows.length || rows.length > 30 || !(unit in UNITS)) throw new Error('rows');
    const points = rows.map(row => {
      const x = dateValue(row.observation_key), raw = row.value;
      if (typeof raw !== 'string' || raw.trim() === '') throw new Error('value');
      const y = Number(raw) * (unit === 'fraction' ? 100 : 1);
      if (!Number.isFinite(y)) throw new Error('value');
      return {x, y, raw, label: row.observation_key, revision: row.revised_from ? '수정 관찰' : row.superseded_from ? '당일 표본 교체' : ''};
    });
    const xs = [], ys = [], indices = [];
    if (points.length === 1) { xs.push(points[0].x - DAY); ys.push(null); indices.push(null); }
    points.forEach((point, i) => {
      if (i && point.x <= points[i - 1].x) throw new Error('order');
      if (i && point.x - points[i - 1].x > DAY) { xs.push(points[i - 1].x + DAY); ys.push(null); indices.push(null); }
      point.index = xs.length; xs.push(point.x); ys.push(point.y); indices.push(i);
    });
    if (points.length === 1) { xs.push(points[0].x + DAY); ys.push(null); indices.push(null); }
    return {points, data: [xs, ys], indices, range: [xs[0], xs.at(-1)]};
  }
  function ticks(min, max, width, temporal) {
    if (!temporal) return width < 500 ? [0, 10, 20, 30] : [0, 5, 10, 15, 20, 25, 30];
    if (width < 500) return [min, max];
    const step = Math.max(1, Math.ceil((max - min) / DAY / 4)) * DAY;
    const result = [min];
    for (let x = min + step; x < max - step / 2; x += step) result.push(x);
    result.push(max); return result;
  }
  function scaleLabel(range, unit) {
    const largest = Math.max(...range.map(Math.abs));
    const [divisor, prefix] = largest >= 1e12 ? [1e12, '조 '] : largest >= 1e9 ? [1e9, '십억 '] : largest >= 1e6 ? [1e6, '백만 '] : [1, ''];
    return {divisor, unit: prefix + UNITS[unit]};
  }
  function number(value) {
    if (value !== 0 && (Math.abs(value) < 1e-6 || Math.abs(value) >= 1e15)) return value.toExponential(4);
    return new Intl.NumberFormat('ko-KR', {maximumFractionDigits: 10}).format(value);
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {dateValue, domain, historyData, ticks, scaleLabel};
  if (typeof document === 'undefined') return;
  const assetBase = new URL('.', document.currentScript.src);
  const contexts = new Map();
  let loading = null;
  function vendor() {
    if (loading) return loading;
    const nodes = [];
    loading = Promise.all([
      ['link', 'uPlot.min.css', 'sha256-32MMao1vjur/JktQ9zzlsRT2Rv/ZoLt08EmwoAE1+gQ='], ['script', 'uPlot.iife.min.js', 'sha256-GcjUxq2Ikpp59K5J1vcWFWbf0Lo9FcxJXpdPeH63jx8='],
    ].map(([tag, file, integrity]) => new Promise((resolve, reject) => {
      const node = document.createElement(tag); nodes.push(node);
      const url = new URL('vendor/uplot-1.6.32/' + file, assetBase);
      node.integrity = integrity; node.crossOrigin = 'anonymous';
      if (tag === 'link') { node.rel = 'stylesheet'; node.href = url.href; }
      else { node.src = url.href; node.async = true; }
      const timer = setTimeout(() => { node.remove(); reject(new Error('timeout')); }, 8000);
      node.onload = () => { clearTimeout(timer); resolve(); };
      node.onerror = () => { clearTimeout(timer); reject(new Error('asset')); };
      document.head.append(node);
    }))).then(() => {
      if (typeof window.uPlot !== 'function') throw new Error('library');
      return window.uPlot;
    }).catch(error => { nodes.forEach(node => node.remove()); loading = null; throw error; });
    return loading;
  }
  const node = (tag, className, text) => {
    const element = document.createElement(tag); element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  };
  function palette() {
    const style = getComputedStyle(document.body);
    return {ink: style.getPropertyValue('--investo-ink').trim() || '#17363b',
      accent: style.getPropertyValue('--investo-accent').trim() || '#007873',
      border: style.getPropertyValue('--investo-border').trim() || '#bccbcd',
      surface: style.getPropertyValue('--investo-surface').trim() || '#ffffff'};
  }
  function setup(figure, spec, details) {
    if (contexts.has(figure)) return;
    const mount = figure.querySelector('[data-chart-mount]');
    const fallback = figure.querySelector('[data-chart-fallback]');
    const status = figure.querySelector('[data-chart-status]');
    const context = {figure, plot: null, dead: false, pending: false, resize: null};
    const controls = node('label', 'insights-chart-selector', '관측값 확인 ');
    const select = document.createElement('select'); select.setAttribute('aria-label', `${spec.title} 관측값 확인`);
    select.dataset.testid = 'insights-chart-observation';
    const placeholder = node('option', '', '관측값 선택'); placeholder.value = ''; placeholder.disabled = true; select.append(placeholder);
    const describe = point => `${point.label} · ${spec.unit === 'fraction' ? number(point.y) + '% (원천 비율 ' + point.raw + ')' : point.raw + ' ' + UNITS[spec.unit]}${point.revision ? ' · ' + point.revision : ''}`;
    spec.points.forEach((point, index) => { const option = node('option', '', describe(point)); option.value = String(index); select.append(option); });
    controls.append(select);
    const readout = node('output', 'insights-chart-readout', describe(spec.points[0]));
    readout.setAttribute('aria-live', 'polite'); readout.dataset.chartReadout = '';
    select.value = '0'; controls.hidden = true; readout.hidden = true;
    mount.after(controls, readout);
    const choose = () => {
      const point = spec.points[Number(select.value)];
      if (!point) return;
      readout.textContent = describe(point);
      context.plot?.setCursor({left: context.plot.valToPos(point.x, 'x'), top: context.plot.valToPos(point.y, 'y')});
    };
    select.addEventListener('change', choose);
    const size = () => ({width: Math.max(280, Math.floor(mount.clientWidth)), height: 300});
    async function start() {
      if (context.dead || context.pending || context.plot || (details && !details.open)) return;
      context.pending = true;
      try {
        const UPlot = await vendor();
        if (context.dead || !figure.isConnected) return;
        const colors = palette(), scaling = scaleLabel(spec.yRange, spec.unit);
        const options = {
          ...size(), padding: [16, 16, 4, 4],
          scales: {x: {time: false, range: () => spec.xRange}, y: {range: () => spec.yRange}},
          axes: [
            {label: spec.xLabel, stroke: colors.ink, font: '12px sans-serif', labelFont: '13px sans-serif', size: 58,
              grid: {show: false}, ticks: {stroke: colors.border},
              splits: u => ticks(spec.xRange[0], spec.xRange[1], u.width, spec.temporal),
              values: (u, values) => values.map(value => spec.temporal ? new Date(value).toISOString().slice(0, 10) : number(value))},
            {label: spec.yLabel + ' (' + scaling.unit + ')', stroke: colors.ink, font: '12px sans-serif', labelFont: '13px sans-serif', size: 62,
              grid: {stroke: colors.border, width: 1}, ticks: {stroke: colors.border},
              values: (u, values) => values.map(value => number(value / scaling.divisor))},
          ],
          series: [{label: spec.xLabel}, {label: spec.title, stroke: colors.accent, width: 2, spanGaps: false,
            points: {show: true, size: 7, width: 2, fill: colors.surface, stroke: colors.accent}}],
          legend: {show: false}, select: {show: false},
          cursor: {drag: {x: false, y: false, setScale: false}, points: {show: false}},
          hooks: {setCursor: [u => {
            const index = spec.indices[u.cursor.idx];
            const point = index == null ? null : spec.points[index];
            if (point) { select.value = String(index); readout.textContent = describe(point); }
            else if (u.cursor.idx != null) { select.value = ''; readout.textContent = '이 날짜에 기록된 관측값이 없습니다.'; }
          }]},
        };
        mount.replaceChildren();
        context.plot = new UPlot(options, spec.data, mount);
        mount.setAttribute('role', 'img'); mount.setAttribute('aria-label', `${spec.title}. 가로축 ${spec.xLabel}, 세로축 ${spec.yLabel} ${scaling.unit}, 선형 눈금. 정확한 값은 관측 선택과 표를 확인하세요.`);
        mount.dataset.chartReady = 'true';
        if (fallback) fallback.setAttribute('hidden', '');
        controls.hidden = false; readout.hidden = false; status.textContent = '';
        if (typeof ResizeObserver !== 'undefined') {
          context.resize = new ResizeObserver(() => {
            if (!figure.isConnected || !context.plot || (details && !details.open)) return;
            const next = size(); if (next.width !== context.plot.width) context.plot.setSize(next);
          }); context.resize.observe(mount);
        }
      } catch {
        status.textContent = '그래프를 표시하지 못했습니다. 정확한 값과 날짜는 표에서 확인하세요.';
      } finally { context.pending = false; }
    }
    const toggle = () => { if (details.open) { start(); if (context.plot) context.plot.setSize(size()); } };
    if (details) details.addEventListener('toggle', toggle);
    context.destroy = () => {
      context.dead = true; context.resize?.disconnect(); context.plot?.destroy(); context.plot = null;
      select.removeEventListener('change', choose); details?.removeEventListener('toggle', toggle);
      controls.remove(); readout.remove();
    };
    context.retheme = () => {
      context.resize?.disconnect(); context.plot?.destroy(); context.plot = null;
      mount.replaceChildren(); if (fallback) fallback.removeAttribute('hidden'); start();
    };
    contexts.set(figure, context); start();
  }
  function history(details, rows, definition, moduleId) {
    const metric = definition.metric;
    const prepared = historyData(rows, metric.unit);
    const yRange = domain(prepared.points.map(p => p.y), metric.metric_id === 'fear_greed_index' ? [0, 100] : null);
    const scaling = scaleLabel(yRange, metric.unit);
    const figure = node('figure', 'insights-plot'); figure.dataset.historyPlot = '';
    figure.append(node('figcaption', '', `${metric.label} · ${rows.length}개 관측`));
    figure.append(node('p', 'insights-attribution', definition.attribution || metric.provider));
    const xLabel = moduleId === 'crypto' ? '수집 표본 UTC일' : '원천 관측일';
    figure.append(node('p', 'insights-axis-note', `가로축: ${xLabel}, 실제 날짜 간격 · 세로축: ${scaling.unit}, 선형 ${number(yRange[0] / scaling.divisor)}~${number(yRange[1] / scaling.divisor)} ${metric.metric_id === 'fear_greed_index' ? '고정 범위' : '자동 범위, 0에 고정하지 않음'}.`));
    figure.append(node('p', 'insights-chart-note', rows.length === 1 ? '관측 1건입니다. 변화나 추세를 판단할 수 없습니다.' : '비어 있는 날짜는 선을 끊어 표시합니다. 사이 날짜의 값을 채우지 않습니다.'));
    const mount = node('div', 'insights-plot-canvas'); mount.dataset.chartMount = ''; mount.tabIndex = 0;
    const status = node('p', '', ''); status.dataset.chartStatus = ''; status.setAttribute('role', 'status');
    figure.append(mount, status); details.append(figure);
    queueMicrotask(() => {
      if (figure.isConnected) setup(figure, {...prepared, xRange: prepared.range, yRange, temporal: true, title: metric.label, unit: metric.unit, xLabel, yLabel: '관측값'}, details);
    });
  }
  function initialize() {
    for (const [figure, context] of contexts) if (!figure.isConnected) { context.destroy(); contexts.delete(figure); }
    document.querySelectorAll('[data-curve-chart]').forEach(figure => {
      if (contexts.has(figure)) return;
      const rows = [...figure.querySelectorAll('[data-curve-x]')];
      const points = rows.map((row, index) => ({x: Number(row.dataset.curveX), y: Number(row.dataset.curveY), raw: row.dataset.curveY, label: row.querySelector('th').textContent, index}));
      if (points.length !== 4 || points.some(p => !Number.isFinite(p.x) || !Number.isFinite(p.y))) return;
      const yRange = [Number(figure.dataset.yMin), Number(figure.dataset.yMax)];
      if (yRange.some(v => !Number.isFinite(v)) || yRange[0] >= yRange[1]) return;
      const mount = figure.querySelector('[data-chart-mount]'); mount.classList.add('insights-plot-canvas'); mount.tabIndex = 0;
      setup(figure, {points, data: [points.map(p => p.x), points.map(p => p.y)], indices: [0, 1, 2, 3], xRange: [0, 30], yRange, temporal: false, title: '미 국채 만기별 금리', unit: 'percent', xLabel: '만기 (년)', yLabel: '금리'});
    });
  }
  new MutationObserver(() => {
    for (const [figure, context] of contexts) if (!figure.isConnected) { context.destroy(); contexts.delete(figure); }
  }).observe(document.body, {childList: true, subtree: true});
  new MutationObserver(() => { for (const context of contexts.values()) context.retheme(); }).observe(document.body, {attributes: true, attributeFilter: ['data-md-color-scheme']});
  window.InvestoInsightCharts = {history};
  initialize();
  if (typeof document$ !== 'undefined') document$.subscribe(initialize);
})();
