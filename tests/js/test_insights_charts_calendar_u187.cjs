const test = require('node:test');
const assert = require('node:assert/strict');
const charts = require('../../site_docs/assets/insights-charts.js');
const calendar = require('../../site_docs/assets/insights-calendar.js');
const DAY = 86400000;
const row = (day, value) => ({observation_key: day, value});

test('calendar uses literal dates across leap/year boundaries', () => {
  assert.equal(calendar.addDays('2028-02-28', 1), '2028-02-29');
  assert.equal(calendar.addDays('2028-02-29', 1), '2028-03-01');
  assert.equal(calendar.addDays('2026-12-31', 1), '2027-01-01');
});
test('period filtering clips each selected day to its own source window', () => {
  const item = {start: '2026-10-24', end: '2026-11-05', windowStart: '2026-10-25'};
  assert.equal(calendar.includesDay(item, '2026-10-24', 30), false);
  assert.equal(calendar.includesDay(item, '2026-10-31', 7), true);
  assert.equal(calendar.includesDay(item, '2026-11-01', 7), false);
  assert.equal(calendar.includesDay(item, '2026-11-01', 30), true);
});
test('history uses actual day distance and null gaps, never an imputed number', () => {
  const source = [row('2026-10-23', '3.91'), row('2026-10-26', '3.92'), row('2026-10-27', '3.90')];
  const copy = JSON.stringify(source);
  const result = charts.historyData(source, 'percent');
  assert.equal(result.points[1].x - result.points[0].x, 3 * DAY);
  assert.equal(result.points[2].x - result.points[1].x, DAY);
  assert.deepEqual(result.data[1], [3.91, null, 3.92, 3.90]);
  assert.deepEqual(result.indices, [0, null, 1, 2]);
  assert.equal(JSON.stringify(source), copy);
});
test('one observation receives only null axis padding and keeps exact raw value', () => {
  const result = charts.historyData([row('2026-10-25', '50.0000')], 'index');
  assert.deepEqual(result.data[1], [null, 50, null]);
  assert.equal(result.points.length, 1);
  assert.equal(result.points[0].raw, '50.0000');
  assert.equal(result.points[0].index, 1);
});
test('fraction display is explicitly scaled while source text stays intact', () => {
  const result = charts.historyData([row('2026-10-25', '-0.0001')], 'fraction');
  assert.equal(result.points[0].y, -.01);
  assert.equal(result.points[0].raw, '-0.0001');
});
test('fixed FNG domain is 0-100 and refuses out-of-domain data', () => {
  assert.deepEqual(charts.domain([49, 50], [0, 100]), [0, 100]);
  assert.throws(() => charts.domain([101], [0, 100]));
});
test('flat, negative and narrow data have finite containing axes', () => {
  for (const values of [[0], [-.01, -.02], [4, 4], [4.001, 4.002]]) {
    const [lo, hi] = charts.domain(values);
    assert.ok(Number.isFinite(lo) && Number.isFinite(hi));
    assert.ok(lo < Math.min(...values) && hi > Math.max(...values));
  }
});
test('invalid, duplicate and reversed dates cannot produce a chart', () => {
  assert.throws(() => charts.dateValue('2026-02-30'));
  assert.throws(() => charts.historyData([row('2026-10-25', '1'), row('2026-10-25', '2')], 'percent'));
  assert.throws(() => charts.historyData([row('2026-10-25', '1'), row('2026-10-24', '2')], 'percent'));
  assert.throws(() => charts.historyData([row('2026-10-25', '')], 'percent'));
  assert.throws(() => charts.domain([Infinity]));
});
test('temporal ticks preserve endpoints and numeric maturity ticks are in years', () => {
  const lo = charts.dateValue('2026-10-23'), hi = charts.dateValue('2026-11-04');
  assert.deepEqual(charts.ticks(lo, hi, 390, true), [lo, hi]);
  const ticks = charts.ticks(lo, hi, 700, true);
  assert.equal(ticks[0], lo); assert.equal(ticks.at(-1), hi);
  assert.ok(ticks.every(v => (v - lo) % DAY === 0));
  assert.deepEqual(charts.ticks(0, 30, 390, false), [0, 10, 20, 30]);
});
test('large currency axes state their magnitude', () => {
  assert.deepEqual(charts.scaleLabel([2e12, 3e12], 'usd'), {divisor: 1e12, unit: '조 USD'});
  assert.deepEqual(charts.scaleLabel([0, 100], 'index'), {divisor: 1, unit: '지수'});
});
