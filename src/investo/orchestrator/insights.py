"""Opt-in configuration and private capture, before any legacy consumer."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from pydantic import TypeAdapter

from investo.models.coverage import SourceOutcome
from investo.models.insights import InsightSourceQualification, ModuleId, SourceInsightEnvelope
from investo.models.items import NormalizedItem


@dataclass(frozen=True, slots=True)
class InsightsConfig:
    mode: Literal["off", "shadow", "active"] = "off"
    modules: tuple[ModuleId, ...] = ("macro",)

    def __post_init__(self) -> None:
        object.__setattr__(self, "modules", tuple(self.modules))
        if self.mode not in {"off", "shadow", "active"}:
            raise ValueError("invalid INVESTO_INSIGHTS_MODE")
        if (
            not self.modules
            or len(set(self.modules)) != len(self.modules)
            or set(self.modules) - {"macro", "calendar", "crypto"}
        ):
            raise ValueError("invalid INVESTO_INSIGHTS_MODULES")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> InsightsConfig:
        env = os.environ if env is None else env
        return cls(
            cast('Literal["off", "shadow", "active"]', env.get("INVESTO_INSIGHTS_MODE", "off")),
            cast(
                "tuple[ModuleId, ...]",
                tuple(m.strip() for m in env.get("INVESTO_INSIGHTS_MODULES", "macro").split(",")),
            ),
        )


@dataclass(frozen=True, slots=True)
class InsightCapture:
    envelopes: tuple[SourceInsightEnvelope, ...]
    outcomes: tuple[SourceOutcome, ...]


def capture_insights(
    items: Sequence[NormalizedItem], outcomes: Sequence[SourceOutcome]
) -> tuple[list[NormalizedItem], InsightCapture]:
    captured = []
    clean = []
    for item in items:
        envelope = item.insight_envelope
        if envelope is not None:
            # Missing collector origin (e.g. legacy DI) cannot establish truth.
            if (
                envelope.source_name == item.source_name
                and envelope.origin_adapter_name is not None
            ):
                captured.append(envelope)
            clean.append(item.model_copy(update={"insight_envelope": None}))
        else:
            clean.append(item)
    return clean, InsightCapture(tuple(captured), tuple(outcomes))


class InsightQualificationError(ValueError):
    """Expected malformed permission configuration."""


def load_qualifications(
    path: Path = Path("ops/insights_source_qualification.json"),
) -> tuple[InsightSourceQualification, ...]:
    if path.stat().st_size > 256 * 1024:
        raise InsightQualificationError("qualification cap exceeded")
    with path.open("rb") as stream:
        raw = stream.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024:
        raise InsightQualificationError("qualification cap exceeded")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InsightQualificationError("invalid qualification JSON") from exc
    if not isinstance(data, dict):
        raise InsightQualificationError("invalid qualification object")
    if set(data) != {"schema_version", "qualifications"} or data["schema_version"] != 1:
        raise InsightQualificationError("invalid qualification schema")
    rows = TypeAdapter(tuple[InsightSourceQualification, ...]).validate_python(
        data["qualifications"]
    )
    keys = {(row.source_name, row.endpoint, row.field_scope) for row in rows}
    if len(rows) > 128 or len(keys) != len(rows):
        raise InsightQualificationError("invalid qualification scopes")
    return rows
