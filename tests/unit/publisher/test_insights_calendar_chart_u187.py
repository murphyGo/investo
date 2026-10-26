"""Presentation semantics, not new observations or scheduled acceptance."""

import base64
import hashlib
import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from investo.models.insights import canonical_bytes
from investo.models.insights_events import BEA_RECIPES, FED_RECIPES
from investo.publisher.insights.calendar import render_calendar
from investo.publisher.insights.calendar_grid import calendar_bounds, on_day
from investo.publisher.insights.chart_view import render_yield_curve, yield_domain
from tests._helpers.macro_insights import module as macro_module
from tests._helpers.upcoming_insights import exact, local, module


def test_calendar_cross_year_keeps_date_only_and_kst_in_separate_dates():
    now = datetime(2026, 12, 31, 16, tzinfo=UTC)
    rows = (
        FED_RECIPES["meeting"].event(local(date(2026, 12, 31)), "fed:year-end"),
        BEA_RECIPES["gdp"].event(exact(now), "bea:year-end"),
    )
    current = module(rows, now=now)
    before = canonical_bytes(current)
    html = render_calendar(current)
    assert 'data-calendar-month="2026-12"' in html
    assert 'data-calendar-month="2027-01"' in html
    assert 'data-calendar-initial-month="2027-01"' in html
    local_row = next(r for r in current.events if r.time.precision == "date")
    exact_row = next(r for r in current.events if r.time.precision == "exact")
    assert on_day(local_row, date(2026, 12, 31), now)
    assert not on_day(local_row, date(2027, 1, 1), now)
    assert on_day(exact_row, date(2027, 1, 1), now)
    assert "01:00 KST" in html and "미 동부 · 시간 미정" in html
    assert "종일" not in html
    assert canonical_bytes(current) == before


def test_period_days_are_clipped_to_the_published_window():
    now = datetime(2026, 10, 25, 12, tzinfo=UTC)
    event = FED_RECIPES["meeting"].event(local(date(2026, 10, 24), date(2026, 10, 28)), "fed:range")
    row = module((event,), now=now).events[0]
    assert not on_day(row, date(2026, 10, 24), now)
    assert on_day(row, date(2026, 10, 25), now)
    assert on_day(row, date(2026, 10, 28), now)
    assert not on_day(row, date(2026, 10, 29), now)
    html = render_calendar(module((event,), now=now))
    assert html.count('data-event="') == 1
    assert html.count('href="#calendar-event-0"') == 4


def test_empty_leap_month_has_calendar_boundaries_and_no_fabricated_events():
    now = datetime(2028, 2, 28, 12, tzinfo=UTC)
    html = render_calendar(module((), now=now))
    assert 'data-calendar-day="2028-02-29"' in html
    assert 'data-calendar-day="2028-03-28"' in html
    assert 'data-calendar-day="2028-03-29"' not in html
    assert "범위 밖" in html and 'data-event="' not in html
    assert calendar_bounds(now) == (date(2028, 2, 28), date(2028, 3, 28))


def test_calendar_day_links_have_unique_targets_and_default_thirty_days():
    html = render_calendar(module())
    targets = re.findall(r'id="(calendar-event-\d+)"', html)
    assert len(targets) == len(set(targets)) == len(module().events)
    assert all(target in targets for target in re.findall(r'href="#(calendar-event-\d+)"', html))
    assert 'data-days="30" aria-pressed="true"' in html
    assert 'scope="col">일</th>' in html
    assert "<noscript>" in html and "KST" in html and "동부" in html


def test_curve_uses_proportional_maturities_and_named_linear_domain():
    current = macro_module()
    rows = {row.metric_id: row for row in current.metrics}
    html = render_yield_curve(rows)
    coords = re.search(r'<polyline points="([^"]+)"', html)[1]
    xs = [float(pair.split(",")[0]) for pair in coords.split()]
    assert (xs[1] - xs[0]) / (xs[-1] - xs[0]) == pytest.approx(1.75 / 29.75, abs=1e-5)
    assert (xs[2] - xs[0]) / (xs[-1] - xs[0]) == pytest.approx(9.75 / 29.75, abs=1e-5)
    assert "가로축: 만기(년)" in html and "세로축: 금리(%)" in html
    assert "선형" in html and "자동 범위" in html
    assert "<svg" in html and "<table>" in html
    assert 'data-curve-x="0.25"' in html


@pytest.mark.parametrize(
    "values", [["0", "0", "0", "0"], ["-1", "-.5", ".1", ".2"], ["3.999", "4", "4.001", "4.002"]]
)
def test_axis_contains_flat_negative_and_narrow_values_without_changing_them(values):
    original = list(map(Decimal, values))
    lo, hi, step = yield_domain(original)
    assert lo < min(original) <= max(original) < hi and step > 0
    assert original == list(map(Decimal, values))


def test_incomplete_curve_has_only_exact_table_and_honest_message():
    rows = {row.metric_id: row for row in macro_module().metrics if row.metric_id != "ust_30y"}
    html = render_yield_curve(rows)
    assert "<table>" in html and "data-curve-chart" not in html
    assert "같은 날짜" in html


def test_vendor_bytes_license_budget_and_sri_match_pinned_provenance():
    root = Path("site_docs/assets/vendor/uplot-1.6.32")
    record = json.loads((root / "provenance.json").read_text())
    loader = Path("site_docs/assets/insights-charts.js").read_text()
    assert record["version"] == "1.6.32" and record["license"] == "MIT"
    total = 0
    for name, info in record["files"].items():
        data = (root / name).read_bytes()
        assert len(data) == info["bytes"]
        assert hashlib.sha256(data).hexdigest() == info["sha256"]
        if name.endswith((".js", ".css")):
            total += len(data)
            assert "sha256-" + base64.b64encode(hashlib.sha256(data).digest()).decode() in loader
    assert total < 80 * 1024
    assert "Copyright" in (root / "LICENSE.txt").read_text()


def test_high_precision_curve_terminates_with_bounded_ticks_and_preserves_values():
    rows = {row.metric_id: row for row in macro_module().metrics}
    for index, name in enumerate(("ust_3m", "ust_2y", "ust_10y", "ust_30y")):
        value = Decimal("4." + "1" * 59 + str(index))
        row = rows[name].model_copy(update={"value": value})
        rows[name] = type(row).model_validate_json(canonical_bytes(row))
    html = render_yield_curve(rows)
    assert 2 <= html.count('class="insights-chart-grid"') <= 12
    assert all(str(rows[name].value) in html for name in ("ust_3m", "ust_2y", "ust_10y", "ust_30y"))


@pytest.mark.parametrize("exact_time", [False, True])
def test_distributed_max_calendar_fits_existing_budget(exact_time):
    from datetime import timedelta

    from investo.publisher.insights.store import prepare_bundle

    now = datetime(2026, 10, 25, 12, tzinfo=UTC)
    rows = tuple(
        FED_RECIPES["speech"].event(
            exact(now + timedelta(days=i % 29))
            if exact_time
            else local(now.date() + timedelta(days=i % 29)),
            f"fed:distributed-{i}",
        )
        for i in range(128)
    )
    current = module(rows, now=now)
    assert len(current.events) == 128
    prepared = prepare_bundle((current,), {})
    html = dict(prepared.files)[Path("site_docs/insights/calendar/index.md")]
    assert len(html) <= 120 * 1024
    assert html.count(b'data-event="') == 128
