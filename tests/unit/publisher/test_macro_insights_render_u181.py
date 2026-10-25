from decimal import Decimal
from gzip import compress
from html import escape
from pathlib import Path

from investo.models.insights import (
    HistoryDefinition,
    InsightHistory,
    InsightHistoryRow,
    InsightTime,
    SourceInsightMetric,
    canonical_bytes,
    digest,
)
from investo.models.insights_calendar import previous_business_day
from investo.orchestrator.insights_projection import update_history
from investo.publisher.insights.macro import five_day_change, render_awaiting, render_macro
from investo.publisher.insights.store import prepare_bundle, validate_bundle
from tests._helpers.macro_insights import module, qualifications


def history_for(row, *, missing=False, revised=False):
    days = [row.time.local_date]
    for _ in range(5):
        days.append(previous_business_day(days[-1], row.calendar_policy))
    rows = []
    for i, day in enumerate(days):
        if missing and i == 5:
            continue
        clock = InsightTime(
            basis="effective_date",
            precision="date",
            local_date=day,
            source_timezone="America/New_York",
        )
        value = row.value - Decimal(i) * Decimal(".04")
        rows.append(
            InsightHistoryRow(
                definition_key=row.comparison_key(),
                observation_key=day.isoformat(),
                value=value,
                time=clock,
                record_hash=digest(
                    canonical_bytes({"value": str(value), "time": clock.model_dump(mode="json")})
                ),
                revised_from="0" * 64 if revised and i == 5 else None,
            )
        )
    return InsightHistory(
        module="macro",
        definitions=(
            HistoryDefinition(
                key=row.comparison_key(),
                metric=SourceInsightMetric.model_validate(
                    {
                        k: v
                        for k, v in row.model_dump().items()
                        if k in SourceInsightMetric.model_fields
                    }
                ),
                attribution=row.attribution,
            ),
        ),
        rows=tuple(rows),
    )


def test_exact_five_business_days_and_missing_or_revision_suppression():
    row = next(r for r in module().metrics if r.metric_id == "ust_2y")
    assert five_day_change(row, history_for(row)) == Decimal("20.00")
    assert five_day_change(row, history_for(row, missing=True)) is None
    assert five_day_change(row, history_for(row, revised=True)) is None
    assert five_day_change(row.model_copy(update={"last_good": True}), history_for(row)) is None


def test_thirteen_cards_units_clocks_and_no_inline_history():
    current = module()
    history = update_history(current, None, qualifications())
    html = render_macro(current, history)
    assert html.count("data-metric=") == 13
    assert "20.00" in html and "bp" in html and "계절조정" in html
    assert "2026-09 대상" in html and "최신 여부 미확인" in html
    assert "<svg" in html and "<table>" in html and 'scope="col"' in html
    assert "data-history-loader" in html and "data-current-hash" in html
    assert "관측 이력 원본(JSON)" in html
    assert "실제 관측 순서로" not in html  # History data is loaded only after interaction.
    assert len(html.encode()) < 100 * 1024


def test_awaiting_has_no_fabricated_data_or_operational_clock():
    html = render_awaiting()
    assert html.count("data-metric=") == 13
    assert "첫 자료를 준비 중" in html
    assert "insights-snapshot:" not in html and "KST" not in html
    assert "_data/macro/history.json" not in html


def test_escaped_attribution_and_bundle_hash_identity():
    current = module()
    row = current.metrics[0].model_copy(update={"attribution": "<script>alert(1)</script>"})
    altered = type(current)(
        **{**current.model_dump(), "snapshot_id": "", "metrics": (row, *current.metrics[1:])}
    )
    html = render_macro(altered)
    assert "<script>" not in html and "&lt;script&gt;" in html
    history = update_history(current, None, qualifications())
    prepared = prepare_bundle((current,), {"macro": history})
    manifest, _, _ = validate_bundle(dict(prepared.files))
    assert manifest.modules[0].snapshot_id == current.snapshot_id


def test_critical_assets_budget_and_scoped_css():
    css = Path("site_docs/assets/insights.css").read_bytes()
    js = Path("site_docs/assets/insights.js").read_bytes()
    assert len(compress(css)) + len(compress(js)) < 50 * 1024
    assert ".insights-page" in css.decode() and "overflow-x: hidden" not in css.decode()
    assert "crypto.subtle.digest" in js.decode() and "entry.snapshot_id" in js.decode()


def test_related_link_uses_actual_proven_archived_date():
    from datetime import date

    html = render_macro(module(), briefing_date=date(2026, 10, 8))
    assert "../../archive/us-equity/2026/10/2026-10-08/" in html
    assert "보관 시황 · 2026-10-08" in html


def test_nyfed_notices_are_prominent_and_follow_current_and_history_data():
    from investo.orchestrator.insights import load_qualifications

    # Exercise the planned activation without opening production policy before
    # the renderer supporting the required notice is installed.
    rights = tuple(
        q.model_copy(
            update={
                "display_allowed": True,
                "public_git_history_allowed": True,
                "retention_allowed": True,
            }
        )
        if q.source_name == "nyfed-reference-rates"
        else q
        for q in load_qualifications()
    )
    current = module(rights=rights)
    notice = next(q.attribution for q in rights if q.source_name == "nyfed-reference-rates")
    html = render_macro(current)
    assert html.count(escape(notice)) == 1
    assert html.index(escape(notice)) < html.index('data-metric="sofr"')
    for mid in ("sofr", "effr", "sofr_effr_bp"):
        start = html.index(f'data-metric="{mid}"')
        card = html[start : html.index("</article>", start)]
        assert ("Investo 계산값" in card) == (mid == "sofr_effr_bp")
    history = update_history(current, None, rights)
    assert all(
        d.attribution == notice
        for d in history.definitions
        if d.metric.source_name == "nyfed-reference-rates"
    )
    assert "../_data/NOTICE.txt" in html
    assert len(canonical_bytes(current)) < 256 * 1024 and len(html.encode()) < 100 * 1024


def test_nyfed_source_license_and_non_affiliation_notice_are_preserved():
    from investo.orchestrator.insights import load_qualifications

    rows = [q for q in load_qualifications() if q.source_name == "nyfed-reference-rates"]
    assert len(rows) == 3
    assert {d.public_id for q in rows for d in q.definitions} == {"sofr", "effr", "sofr_effr_bp"}
    assert len({q.attribution for q in rows}) == 1
    notice = rows[0].attribution
    assert len(notice) <= 1000
    for required in (
        "© 2026 Federal Reserve Bank of New York",
        "subject to the Terms of Use posted at newyorkfed.org",
        "not responsible for publication",
        "Investo is not affiliated with the New York Fed",
        "DTCC Solutions LLC",
        "Investo calculation, not a New York Fed reference rate",
    ):
        assert required in notice
    assert notice in Path("site_docs/insights/_data/NOTICE.txt").read_text()
    assert "provider-specific terms and notices" in Path("README.md").read_text()


def test_nyfed_five_day_changes_are_labeled_as_investo_calculations():
    current = module()
    for mid in ("sofr", "effr"):
        row = next(r for r in current.metrics if r.metric_id == mid)
        html = render_macro(current, history_for(row))
        start = html.index(f'data-metric="{mid}"')
        card = html[start : html.index("</article>", start)]
        assert five_day_change(row, history_for(row)) == Decimal("20.00")
        assert "Investo 계산 · 5원천 영업일 변화 +20.00 bp" in card
        # The observation remains the source value; only its comparison is ours.
        assert f"{row.value:,f} <small>%</small>" in card
        assert "원천기관이 발표한 금리차가 아닙니다" not in card
