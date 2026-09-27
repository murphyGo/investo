"""Closed qualifications and bounded opt-in enrichment policy."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from investo.models.enrichment import EnrichmentPolicy, EnrichmentQualification, SourceQualification


def qualification_record(source: str = "cftc-policy-rss") -> SourceQualification:
    fed = source in {"fomc-rss", "fed-speech-rss"}
    host = "www.federalreserve.gov" if fed else "www.cftc.gov"
    path = (
        "/newsevents/pressreleases/"
        if source == "fomc-rss"
        else ("/newsevents/speech/" if source == "fed-speech-rss" else "/PressRoom/PressReleases/")
    )
    return SourceQualification.model_validate(
        {
            "source_name": source,
            "checked_at": datetime(2026, 9, 26, tzinfo=UTC),
            "official_discovery_url": f"https://{host}/feeds/index.htm",
            "allowed_host": host,
            "allowed_path": path,
            "content_type": "text/html",
            "public_rights_basis": "Synthetic public-domain government text qualification.",
            "extraction_selector_version": "fed-article-body-v1"
            if fed
            else "cftc-press-article-body-v1",
            "fixture_sha256": "a" * 64,
            "status": "qualified",
            "reason": "Synthetic qualified fixture.",
        }
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"max_requests": 7},
        {"concurrency": 3},
        {"request_timeout_s": 9},
        {"total_budget_s": 21},
        {"max_response_bytes": 512001},
        {"max_items_per_source": 3},
        {"max_excerpt_chars": 1201},
        {"max_redirects": 2},
        {"max_requests": True},
        {"total_budget_s": float("nan")},
    ],
)
def test_policy_cannot_expand_approved_limits(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(EnrichmentPolicy(), **changes)


def test_policy_default_off_and_activation_requires_explicit_operational_gate() -> None:
    assert EnrichmentPolicy.from_env({}).mode == "off"
    with pytest.raises(ValueError, match="operational approval"):
        EnrichmentPolicy("active").validate_activation()
    EnrichmentPolicy("shadow").validate_activation()
    with pytest.raises(ValueError):
        EnrichmentPolicy.from_env({"INVESTO_EVENT_ENRICHMENT_MODE": "yes"})
    policy = EnrichmentPolicy()
    with pytest.raises(FrozenInstanceError):
        policy.max_requests = 9  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"fixture_sha256": None},
        {"public_rights_basis": None},
        {"allowed_host": "127.0.0.1"},
        {"allowed_path": "/PressRoom/../"},
        {"allowed_path": "/"},
        {"official_discovery_url": "https://www.cftc.gov.attacker.invalid/feed"},
        {"checked_at": datetime(2026, 9, 26)},
        {"raw_html": "body"},
    ],
)
def test_qualification_requires_closed_scoped_official_evidence(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SourceQualification.model_validate(qualification_record().model_dump() | changes)


def test_qualification_duplicate_source_is_rejected() -> None:
    row = qualification_record()
    with pytest.raises(ValidationError, match="duplicate"):
        EnrichmentQualification(sources=(row, row))
