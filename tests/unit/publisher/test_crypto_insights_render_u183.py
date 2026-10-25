"""Synthetic current-only rendering, explicit economics, history and size budgets."""

import gzip
from datetime import timedelta
from pathlib import Path

import pytest

from investo.models.insights import canonical_bytes
from investo.orchestrator.insights_projection import update_history
from investo.publisher.insights.crypto import render_awaiting_crypto, render_crypto
from investo.publisher.insights.store import module_paths, prepare_bundle, validate_bundle
from tests._helpers.crypto_insights import NOW, module, qualifications


def test_fraction_is_cycle_percent_and_provider_scope_is_visible():
    html = render_crypto(module())
    assert "0.01 <small>%</small>" in html
    assert "BTCUSDT · 선형 무기한" in html
    assert "지시적 관찰 · 적용 주기" in html
    assert "확정 정산값·24시간 평균·연율이 아닙니다." in html
    assert "순자금 유입·거래활동을 뜻하지 않습니다." in html
    assert "실제 시장가격 평가액·순유입이 아닙니다." in html
    assert "원천 갱신시각 미상 · 수집 구간 관찰" in html
    assert (
        "Source" not in html
    )  # synthetic attribution is explicitly synthetic, never production evidence
    assert "Synthetic permission fixture only" in html


def test_current_only_first_release_has_no_fabricated_change_or_inline_history():
    html = render_crypto(module())
    assert html.count("data-metric=") == 7
    assert "자료 부족 또는 비교 제외" in html
    assert "data-load-history hidden" in html
    assert "history.rows" not in html and "polyline" not in html


def test_initial_awaiting_has_no_fake_numbers_clocks_or_snapshot():
    html = render_awaiting_crypto()
    assert "자료를 기다립" in html
    assert "snapshot" not in html and "current.json" not in html and "2026-" not in html


def test_bundle_verifies_identity_history_and_disclaimer():
    current = module()
    history = update_history(current, None, qualifications())
    prepared = prepare_bundle((current,), {"crypto": history})
    files = dict(prepared.files)
    _, loaded, histories = validate_bundle(files)
    assert loaded["crypto"] == current and histories["crypto"] == history
    index = files[module_paths("crypto")[1]]
    assert current.snapshot_id.encode() in index
    assert len(index) < 100 * 1024 and len(canonical_bytes(current)) < 256 * 1024
    assert (
        len(gzip.compress(Path("site_docs/assets/insights.css").read_bytes()))
        + len(gzip.compress(Path("site_docs/assets/insights.js").read_bytes()))
        < 20 * 1024
    )


def test_last_good_never_claims_latest_or_seven_day_change_and_text_is_escaped():
    old = module()
    current = module(
        (),
        now=NOW + timedelta(hours=40),
        previous=old,
        statuses={
            s: "failed"
            for s in (
                "coingecko-global-market",
                "defillama-market-structure",
                "bybit-derivatives",
                "okx-derivatives",
                "alternative-fng",
            )
        },
    )
    html = render_crypto(current)
    assert "이전 검증 관찰" in html and "관측 시점 경과" in html
    row = current.metrics[0].model_copy(update={"attribution": "<script>alert(1)</script>"})
    html = render_crypto(current.model_copy(update={"metrics": (row,)}))
    assert "<script>alert" not in html and "&lt;script&gt;" in html


def test_renderer_rejects_other_module():
    from tests._helpers.macro_insights import module as macro_module

    with pytest.raises(ValueError, match="crypto module"):
        render_crypto(macro_module())
