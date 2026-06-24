"""Public quality / accuracy dashboard pages (u32).

The quality dashboard (``site_docs/quality.md``) and the forecast
accuracy page (``site_docs/accuracy.md``) are regenerated on every
successful publish from the trailing-window KPIs / forecast log.

Move-only split out of the original ``site_index.py`` module (u82).

The page-path defaults are resolved at *call time* through the package
namespace (``investo.publisher.site_index``) — not at function-definition
time — so a test-side ``monkeypatch.setattr(site_index, "QUALITY_PAGE_PATH",
...)`` against the package root reaches these writers exactly as it did
when the function lived in the single-file module.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path


def update_quality_page(
    target_date: date,
    *,
    coverage_path: Path,
    archive_root: Path,
    quality_history_path: Path | None = None,
    quality_page_path: Path | None = None,
    window_days: int = 7,
) -> Path:
    """Regenerate ``site_docs/quality.md`` from the trailing-window KPIs.

    Pure I/O: reads ``coverage_path`` + scans ``archive_root``; writes
    a fresh page at ``quality_page_path``. Returns the written path.
    The file is overwritten in place — no marker-bracketed merge — so
    running the function twice with the same inputs leaves the file
    byte-identical.

    ``quality_page_path`` defaults to the module-level
    :data:`QUALITY_PAGE_PATH` resolved at *call time* (not at function
    definition time) so test-side ``monkeypatch.setattr`` redirection
    reaches this writer.
    """
    import investo.publisher.site_index as _pkg
    from investo.briefing.quality_eval import (
        compute_quality_history,
        compute_quality_kpis,
        render_quality_page,
    )
    from investo.briefing.quality_history import resolve_quality_history_path
    from investo.publisher.quality_consistency import reconcile_kpis_with_history
    from investo.visuals.quality_sparkline import render_quality_sparkline

    target = quality_page_path if quality_page_path is not None else _pkg.QUALITY_PAGE_PATH
    history_target = (
        quality_history_path if quality_history_path is not None else resolve_quality_history_path()
    )
    kpis = compute_quality_kpis(
        target_date,
        coverage_path=coverage_path,
        archive_root=archive_root,
        window_days=window_days,
    )
    # u69 — the trailing-window KPIs are computed from ``coverage.jsonl``.
    # When that file is empty / lagging but the canonical quality-history
    # row for the date already records failed sources, the dashboard must
    # not render ``실패한 소스 누적 = 0`` (a healthier-looking surface than
    # the archive). Reconcile the failed-source floor up to the canonical
    # history evidence so the dashboard agrees with the same snapshot the
    # publish-boundary gate validates against.
    kpis = reconcile_kpis_with_history(
        kpis,
        target_date=target_date,
        history_path=history_target,
    )
    history_rows = compute_quality_history(30, history_path=history_target, today=target_date)
    sparkline = render_quality_sparkline(history_rows).decode("utf-8")
    body = _render_quality_page_with_history(render_quality_page(kpis), sparkline)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def update_accuracy_page(
    *,
    forecast_log_path: Path,
    accuracy_page_path: Path | None = None,
) -> Path:
    """Regenerate the public forecast-accuracy page."""
    import investo.publisher.site_index as _pkg
    from investo.briefing.accuracy import (
        PriceMove,
        compute_accuracy,
        render_accuracy_page,
    )
    from investo.models.segments import MarketSegment

    def no_price_data(
        segment: MarketSegment,
        target_date: date,
        window_days: int,
    ) -> PriceMove | None:
        del segment, target_date, window_days
        return None

    target = accuracy_page_path if accuracy_page_path is not None else _pkg.ACCURACY_PAGE_PATH
    body = render_accuracy_page(
        (
            compute_accuracy(7, log_path=forecast_log_path, price_lookup=no_price_data),
            compute_accuracy(30, log_path=forecast_log_path, price_lookup=no_price_data),
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _render_quality_page_with_history(base_body: str, sparkline_svg: str) -> str:
    stripped = base_body.rstrip()
    lines = stripped.splitlines()
    if not lines:
        return stripped + "\n"
    return "\n".join(
        [
            lines[0],
            "",
            sparkline_svg,
            "",
            "## 현재 7일 KPI",
            "",
            *lines[1:],
            "",
            "## 최근 30일 추세",
            "",
            "위 SVG는 매 게시 시점의 소스 라이브니스, 수치 인용, 폴백 비율을 "
            "30일 창으로 표시합니다. 끊어진 구간은 해당 날짜의 게시 이력이 없음을 뜻합니다.",
            "",
        ]
    )
