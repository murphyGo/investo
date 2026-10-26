"""Global budget includes prior usage, source preparation and local wall time."""

import pytest

from investo.briefing.claude_code import RetryBudget
from investo.briefing.errors import BriefingGenerationError
from investo.briefing.event_article_review import ArticleCallBudget
from investo.briefing.generation_contract import GenerationInput
from investo.briefing.watchlist import WatchlistConfig
from investo.models.event_config import EventExecutionConfig
from investo.orchestrator.event_preview import preview_event_briefing
from tests._helpers.event_article_v2 import article_case
from tests._helpers.event_context_v3 import NOW


def test_budget_counts_prior_elapsed_and_local_processing(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("investo.briefing.event_article_review.time.monotonic", lambda: clock[0])
    shared = RetryBudget(total_budget_s=10000, elapsed_s=3000)
    controller = ArticleCallBudget(shared=shared, started_at=1000, preparation_elapsed_s=20)
    shared.record(600)
    clock[0] = 1650  # 600 model + 50 local, in addition to pre-existing usage.
    assert controller.remaining == 230
    with pytest.raises(BriefingGenerationError):
        controller.require(600 + 60)


def test_preparation_and_model_time_are_not_double_counted(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("investo.briefing.event_article_review.time.monotonic", lambda: clock[0])
    shared = RetryBudget(total_budget_s=3900)
    controller = ArticleCallBudget(shared=shared, started_at=100, preparation_elapsed_s=20)
    shared.record(20)
    clock[0] = 150  # model20 + local30.
    assert controller.remaining == 3830


def test_repair_and_review_must_fit_together_inclusive_boundary(monkeypatch):
    monkeypatch.setattr("investo.briefing.event_article_review.time.monotonic", lambda: 100.0)
    controller = ArticleCallBudget(
        shared=RetryBudget(total_budget_s=3900, elapsed_s=2340), started_at=100
    )
    with pytest.raises(BriefingGenerationError):
        controller.require(900 + 600 + 60)
    controller.shared.elapsed_s -= 1
    controller.initial_elapsed_s -= 1
    controller.require(900 + 600 + 60)


@pytest.mark.asyncio
@pytest.mark.parametrize("elapsed,preparation", [(3900, 0), (0, 3240)])
async def test_exhausted_profile_never_invokes_classifier(elapsed, preparation):
    item, draft, _, _ = article_case()

    def forbidden(*args, **kwargs):
        pytest.fail("classifier ran after native budget exhaustion")

    with pytest.raises(BriefingGenerationError, match="budget"):
        await preview_event_briefing(
            GenerationInput(
                target_date=draft.target_date,
                segment=draft.segment,
                items=(item,),
                runner=forbidden,
                budget=RetryBudget(total_budget_s=10000, elapsed_s=elapsed),
                event_preparation_elapsed_s=preparation,
                watchlist_config=WatchlistConfig(),
                event_observed_at=NOW,
                event_generation_policy=EventExecutionConfig(
                    mode="preview", document_schema=3, profile="article_v2"
                ),
            )
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_invalid_budget_cannot_bypass_admission(bad):
    with pytest.raises(ValueError, match="budget"):
        ArticleCallBudget(shared=RetryBudget(elapsed_s=bad), started_at=100)
