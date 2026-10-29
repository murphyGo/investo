"""Written frequencies cannot license new literal numeric claims."""

import pytest

from investo._internal.event_article import validate_composition
from tests._helpers.event_article_v2 import article_case
from tests._helpers.event_context_v3 import NOW


@pytest.mark.parametrize("frequency", ["Semiweekly", "주 2회"])
def test_written_source_frequency_requires_its_original_term(frequency):
    _, draft, composition, _ = article_case(detail="Acme publishes Semiweekly statistics.")
    sentence = composition.narrative.sentences[1].model_copy(
        update={"text": f"Acme는 {frequency} 통계를 공개한다고 설명했습니다."}
    )
    changed = composition.model_copy(
        update={
            "narrative": composition.narrative.model_copy(
                update={
                    "blocks": (
                        composition.narrative.blocks[0],
                        composition.narrative.blocks[1].model_copy(
                            update={"sentences": (sentence,)}
                        ),
                    ),
                }
            ),
        }
    )
    if frequency == "Semiweekly":
        validate_composition(changed, draft.article_readiness[0].packet, draft, observed_at=NOW)
    else:
        with pytest.raises(ValueError, match="fact_unsupported"):
            validate_composition(changed, draft.article_readiness[0].packet, draft, observed_at=NOW)
