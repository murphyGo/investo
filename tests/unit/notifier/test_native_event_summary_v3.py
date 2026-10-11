"""Native Telegram budgets keep required state and whole event sentences."""

from investo.notifier.summary import build_segmented_summary
from investo.publisher.public_document import finalize_public_bundle
from tests._helpers.event_context_v3 import NOW
from tests._helpers.event_document_v3 import native_case, native_context


def test_utf16_budget_preserves_links_disclaimers_and_whole_events():
    cases = []
    for market in ("domestic-equity", "us-equity", "crypto"):
        item, draft = native_case(market)
        article = draft.articles[0].model_copy(
            update={"headline": "Acme Widget 발표 " + "🧪" * 100}
        )
        cases.append((item, draft.model_copy(update={"articles": (article,)})))
    sealed = finalize_public_bundle(
        {draft.segment: draft for _, draft in cases}, context=native_context(*cases)
    ).documents
    summaries = {d.segment: d.notification_summary for d in sealed}
    urls = {d.segment: f"https://example.com/{d.segment}/2026-10-10" for d in sealed}
    text = build_segmented_summary(summaries, site_urls=urls, max_units=950, now_utc=NOW)
    assert len(text.encode("utf-16-le")) // 2 <= 950
    assert "투자 판단과 책임은 본인" in text and "가상자산은 원금 손실" in text
    assert all(url in text for url in urls.values())
    assert text.count("가격 기준일: 확인 불가") == 3
    bullets = [line.removeprefix("• ") for line in text.splitlines() if line.startswith("• ")]
    assert len(bullets) < 3
    assert all(line == cases[0][1].articles[0].headline for line in bullets)
    assert "…" not in text
