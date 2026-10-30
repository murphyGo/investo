"""Deterministic source-backed network activity rows and attribution."""

from __future__ import annotations

from collections.abc import Sequence

from investo.models import NormalizedItem
from investo.models.network_activity import ACTIVITY_METRICS, NetworkActivity


def validated_network_activity(items: Sequence[NormalizedItem]) -> tuple[NetworkActivity, ...]:
    selected: dict[tuple[str, str], NetworkActivity] = {}
    for item in items:
        if item.source_name != "coinmetrics-network-activity":
            continue
        try:
            activity = NetworkActivity.from_metadata(item.raw_metadata)
        except (ValueError, TypeError, OverflowError):
            continue
        key = (activity.asset, activity.metric)
        if key not in selected or selected[key].day < activity.day:
            selected[key] = activity
    return tuple(selected[key] for key in sorted(selected))


def network_activity_rows(activities: Sequence[NetworkActivity]) -> list[str]:
    rows = []
    for activity in activities:
        unit = "개" if activity.metric == "AdrActCnt" else "건"
        label = f"{activity.asset.upper()} 일별 {ACTIVITY_METRICS[activity.metric]}"
        value = f"{int(activity.value):,}{unit} · {activity.day} UTC"
        mean = activity.previous_mean
        value += (
            f" · 직전 7일 평균 {mean}{unit}" if mean is not None else " · 직전 7일 비교 자료 부족"
        )
        rows.append(f"| {label} | {value} |")
    return rows


ACTIVITY_ATTRIBUTION = (
    "일별 네트워크 활동 출처: [Coin Metrics Community](https://github.com/coinmetrics/data) · "
    "[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). "
    "평균은 Investo 계산(소수 첫째 자리 반올림). 조회 시점의 값이며 검토 상태 미제공·수정 가능. "
    "활성 주소는 사용자 수가 아니며 거래 건수는 거래소 매매량이 아님. "
    "ETH는 L1 관측이며, 실시간·가격 방향·과거 시점 공표값을 뜻하지 않음."
)


def render_network_activity_reference(activities: Sequence[NetworkActivity]) -> str:
    if not activities:
        return ""
    return "\n".join(
        [
            "### 일별 네트워크 활동",
            "",
            "| 지표 | 값 |",
            "|------|------|",
            *network_activity_rows(activities),
            "",
            ACTIVITY_ATTRIBUTION,
            "",
        ]
    )
