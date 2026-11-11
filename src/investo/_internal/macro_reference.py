"""Canonical macro reference rows, source identity and publication notices."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from investo.models import NormalizedItem
from investo.models.macro_reference import MACRO_REFERENCES, MacroObservation


def validated_macro_observations(
    items: Sequence[NormalizedItem], *, observed_at: datetime | None = None
) -> tuple[MacroObservation, ...]:
    selected: dict[str, MacroObservation] = {}
    conflicts: set[str] = set()
    for item in items:
        if item.source_name not in MACRO_REFERENCES:
            continue
        try:
            observation = MacroObservation.from_metadata(item.raw_metadata)
        except (ValueError, TypeError, OverflowError):
            continue
        if (
            observation.source_name != item.source_name
            or str(item.url) != observation.url
            or item.category != "macro"
            or item.published_at != observation.collected_at
            or item.scheduled_at is not None
        ):
            continue
        if observed_at is not None and not (
            timedelta(0) <= observed_at - observation.as_of <= timedelta(days=1)
        ):
            continue
        existing = selected.get(item.source_name)
        if existing is not None and existing != observation:
            conflicts.add(item.source_name)
        selected[item.source_name] = observation
    return tuple(
        selected[name] for name in MACRO_REFERENCES if name in selected and name not in conflicts
    )


def macro_reference_rows(observations: Sequence[MacroObservation]) -> list[str]:
    rows = []
    for observation in observations:
        label, unit, _, _ = MACRO_REFERENCES[observation.source_name]
        value = format(Decimal(observation.value), ",f")
        vintage = (
            f" · 발표 버전 {observation.release_vintage}" if observation.release_vintage else ""
        )
        rows.append(f"| {label} | {value} {unit} · 관측 {observation.observation_date}{vintage} |")
    return rows


def macro_reference_notes(observations: Sequence[MacroObservation]) -> str:
    notes = []
    for observation in observations:
        if observation.source_name == "treasury-tga-balance":
            notes.append(
                f"출처: [U.S. Treasury Fiscal Data — Daily Treasury Statement]({observation.url}). "
                "영업일별 정부 계정의 마감 현금 잔액이며 시장 전체 유동성을 뜻하지 않음."
            )
        elif observation.source_name == "nyfed-gscpi":
            notes.append(
                f"출처: [Global Supply Chain Pressure Index]({observation.url}). "
                f"© {observation.collected_at.year} Federal Reserve Bank of New York. "
                "Content from the New York Fed subject to the Terms of Use at newyorkfed.org. "
                "[이용약관](https://www.newyorkfed.org/privacy/termsofuse). "
                "월간 연구 지수로 연준의 공식 추정치가 아님. 선택·표시는 Investo가 구성했으며 "
                "뉴욕연은의 보증·승인을 뜻하지 않음."
            )
        else:
            notes.append(
                "출처: [Office of Financial Research — Financial Stress Index]"
                f"({observation.url}). "
                "일별 지수이며 2영업일 지연 제공."
            )
    if observations:
        notes.append(
            "조회 시점에 제공된 관측값이며 이후 수정 가능. 실시간·새 발표·과거 시점 공표값을 "
            "뜻하지 않으며 지표만으로 자산 가격 방향을 단정하지 않음."
        )
    return "\n\n".join(notes)


def render_macro_reference(observations: Sequence[MacroObservation]) -> str:
    if not observations:
        return ""
    return "\n".join(
        [
            "### 거시 참고 지표",
            "",
            "| 지표 | 값 |",
            "|------|------|",
            *macro_reference_rows(observations),
            "",
            macro_reference_notes(observations),
            "",
        ]
    )
