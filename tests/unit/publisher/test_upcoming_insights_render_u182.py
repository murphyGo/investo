"""Calendar public rendering, precise labels, bounded HTML and no calendar history."""

import gzip
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo.models.insights import canonical_bytes
from investo.models.insights_events import BEA_RECIPES, FED_RECIPES
from investo.publisher.insights.calendar import render_awaiting_calendar, render_calendar
from investo.publisher.insights.store import module_paths, prepare_bundle, validate_bundle
from tests._helpers.upcoming_insights import exact, local, module


def test_exact_kst_and_date_only_are_both_explicit_without_synthetic_nine_am():
    result = module()
    html = render_calendar(result)
    assert "2026-10-29 21:30" in html
    assert "2026-10-27 ~ 2026-10-28" in html
    assert "미국 동부 현지 날짜 · 시간 미정" in html
    # The actual collection clock can be 09:00 KST. Date-only event clocks cannot.
    assert all(e.time.exact_at is None for e in result.events if e.time.precision == "date")
    assert "2026-Q3" in html and "2026-09" in html
    assert 'data-within-seven="false"' in html
    assert "수집 0건·실패·미확인은 일정이 없다는 뜻이 아닙니다." in html
    assert 'data-days="7"' in html and 'data-days="30"' in html
    assert 'data-category-filter="treasury_auction"' in html
    assert "<noscript>" in html and "30일 목록 전체" in html


def test_passed_instant_says_result_unconfirmed_and_no_raw_title_or_url_injection():
    row = BEA_RECIPES["gdp"].event(exact(datetime(2026, 10, 24, 23, tzinfo=UTC)), "bea:gdp")
    html = render_calendar(module((row,)))
    assert "예정 시각 경과 · 결과 미확인" in html
    assert "발표 완료" in html  # only the fixed explanation, never a row status
    malicious = module().events[0].model_copy(update={"label": "<script>alert(1)</script>"})
    value = module().model_copy(update={"events": (malicious,)})
    assert "<script>alert" not in render_calendar(value)
    assert "&lt;script&gt;" in render_calendar(value)


def test_initial_empty_screen_has_no_fabricated_event_clock_or_json_link():
    html = render_awaiting_calendar()
    assert "자료를 기다리고" in html and "시간 미정" in html
    assert "snapshot" not in html and "current.json" not in html and "2026-" not in html


def test_bundle_is_atomic_calendar_current_index_manifest_without_history():
    result = module()
    prepared = prepare_bundle((result,), {})
    files = dict(prepared.files)
    current, index, history = module_paths("calendar")
    assert current in files and index in files and history not in files
    assert result.snapshot_id.encode() in files[index]
    manifest, modules, histories = validate_bundle(files)
    assert modules["calendar"] == result and histories == {}
    assert manifest.modules[0].history_hash is None
    assert len(canonical_bytes(result)) < 256 * 1024


def test_max_selection_fits_html_and_incremental_asset_budget():
    rows = [FED_RECIPES["speech"].event(local(date(2026, 10, 26)), f"fed:{i}") for i in range(128)]
    result = module(rows)
    html = render_calendar(result).encode()
    assert len(html) < 120 * 1024
    assert len(dict(prepare_bundle((result,), {}).files)[module_paths("calendar")[1]]) == len(html)
    css = Path("site_docs/assets/insights.css").read_bytes()
    js = Path("site_docs/assets/insights-calendar.js").read_bytes()
    assert len(gzip.compress(css)) + len(gzip.compress(js)) < 15 * 1024


def test_renderer_rejects_other_module():
    from tests._helpers.macro_insights import module as macro_module

    with pytest.raises(ValueError, match="calendar module"):
        render_calendar(macro_module())
