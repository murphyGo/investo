"""Shared transport helpers for small source-owned macro reference records."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx

from investo.models import NormalizedItem
from investo.models.macro_reference import MACRO_REFERENCES, MacroObservation
from investo.sources._window import FetchWindow
from investo.sources.protocol import SourceFetchError


def reference_cutoff(window: FetchWindow) -> datetime:
    now = datetime.now(UTC)
    return min(now, window.end_utc, window.evidence_received_at or now).astimezone(UTC)


def reference_json(response: httpx.Response, source_name: str) -> Any:
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        return json.loads(response.content, object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SourceFetchError(source_name, "invalid reference JSON", transient=False) from exc


def reference_item(observation: MacroObservation) -> NormalizedItem:
    label, unit, _, _ = MACRO_REFERENCES[observation.source_name]
    vintage = f" 발표 버전 {observation.release_vintage}." if observation.release_vintage else ""
    return NormalizedItem(
        source_name=observation.source_name,
        category="macro",
        title=f"{label} ({observation.observation_date} 관측)",
        summary=(
            f"{observation.value} {unit}.{vintage} 조회 시점에 제공된 관측값이며 수정 가능. "
            "실시간 수치·새 발표·과거 시점 공표값 또는 자산 가격 방향을 뜻하지 않음."
        ),
        url=observation.url,
        published_at=observation.collected_at,
        raw_metadata=observation.metadata(),
    )
