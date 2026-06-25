"""u84 — unit tests for the orchestrator Stage abstraction.

Pins the *shape* of the abstraction introduced in u84 (Step 1) and the
declarative exception-routing table + composition root (Step 5). These
supplement — never replace — the unchanged ``test_run_pipeline.py``
behaviour suite that proves behaviour preservation.
"""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest
from pydantic import HttpUrl, TypeAdapter

from investo.models import PipelineStatus
from investo.orchestrator.stages import (
    PipelineContext,
    Stage,
    StageAction,
    StageResult,
)

_URL = TypeAdapter(HttpUrl).validate_python("https://example.github.io/investo")


def test_pipeline_context_is_frozen() -> None:
    """``PipelineContext`` must be an immutable, inputs-only parameter object."""
    ctx = PipelineContext(target_date=date(2026, 5, 28), site_url_base=_URL)
    assert dataclasses.is_dataclass(ctx)
    params = dataclasses.fields(ctx)
    assert {f.name for f in params} >= {"target_date", "site_url_base"}
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.target_date = date(2026, 1, 1)  # type: ignore[misc]


def test_pipeline_context_carries_no_stage_outputs() -> None:
    """Inputs-only: no field for items / briefings / archive paths.

    Stage-produced values flow via ``StageResult.data``, not the context.
    """
    field_names = {f.name for f in dataclasses.fields(PipelineContext)}
    forbidden = {"items", "briefings", "segment_briefings", "archive_paths", "source_outcomes"}
    assert field_names & forbidden == set()


def test_stage_result_defaults_and_immutability() -> None:
    res: StageResult[int] = StageResult(status="ok", data=7)
    assert res.status == "ok"
    assert res.data == 7
    assert res.error is None
    assert res.stage_notes == {}
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.status = "failed"  # type: ignore[misc]


def test_stage_result_carries_error_for_routable_failure() -> None:
    boom = RuntimeError("boom")
    res: StageResult[None] = StageResult(status="failed", error=boom)
    assert res.error is boom
    assert res.data is None


def test_stage_action_is_a_declarative_routing_entry() -> None:
    action = StageAction(stage="publish", alert=True, status=PipelineStatus.FAILED)
    assert action.stage == "publish"
    assert action.alert is True
    assert action.status is PipelineStatus.FAILED


def test_stage_protocol_runtime_shape() -> None:
    """A minimal object satisfying ``name`` + ``execute`` is a ``Stage``."""

    class _Fake:
        name = "collect"

        async def execute(
            self,
            ctx: PipelineContext,
            accumulated: dict[str, object],
        ) -> StageResult[dict[str, object]]:
            return StageResult(status="ok", data=None)

    fake: Stage = _Fake()
    assert fake.name == "collect"


def test_exception_routing_is_a_declarative_dict() -> None:
    """Step 5 — the exception→action map is a dict keyed by exception type,
    NOT an ``isinstance`` chain. Lives at the pipeline composition root.
    """
    from investo.orchestrator import pipeline as pipeline_module

    routing = pipeline_module.EXCEPTION_ROUTING
    assert isinstance(routing, dict)
    # every key is an exception type, every value a StageAction
    for exc_type, action in routing.items():
        assert isinstance(exc_type, type)
        assert issubclass(exc_type, BaseException)
        assert isinstance(action, StageAction)


def test_quality_consistency_error_routes_as_publish_failure() -> None:
    from investo.orchestrator import pipeline as pipeline_module

    action = pipeline_module.EXCEPTION_ROUTING[pipeline_module.QualityConsistencyError]

    assert action.stage == "publish"
    assert action.alert is True
    assert action.status is PipelineStatus.FAILED
    assert pipeline_module.QualityConsistencyError in pipeline_module._PUBLISH_FAILURES


def test_daily_thesis_consistency_error_routes_as_publish_failure() -> None:
    from investo.orchestrator import pipeline as pipeline_module

    action = pipeline_module.EXCEPTION_ROUTING[pipeline_module.DailyThesisConsistencyError]

    assert action.stage == "publish"
    assert action.alert is True
    assert action.status is PipelineStatus.FAILED
    assert pipeline_module.DailyThesisConsistencyError in pipeline_module._PUBLISH_FAILURES


def test_build_default_stages_is_a_composition_root() -> None:
    """Stages are assembled at a composition root + injectable into the loop."""
    from investo.orchestrator import pipeline as pipeline_module

    stages = pipeline_module.build_default_stages()
    names = [s.name for s in stages]
    # the five catalogued stages exist and are ordered collect → … → notify
    assert names[0] == "collect"
    assert "generate" in names
    assert "publish" in names
    assert "notify_briefing" in names
    # each is a Stage (has name + execute)
    for stage in stages:
        assert hasattr(stage, "name")
        assert hasattr(stage, "execute")
