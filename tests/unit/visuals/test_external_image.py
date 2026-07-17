"""Tests for licensed external image fetching.

u136 Step 4 additions: the license-key non-pollution regression
(Contract #4). The three u136-wired news adapters (yonhap-market /
yahoo-finance-news / theblock-crypto) harvest ``image_*`` presentation
keys but must NEVER emit license-family keys — so
``_manifest_from_item`` stays ``None`` for every harvested item and the
dormant external-image fetch path cannot trigger even when the operator
sets ``INVESTO_EXTERNAL_IMAGE_ASSETS=1``. Pinned here against the real
recorded fixtures the adapters replay.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from investo.models import NormalizedItem
from investo.sources._window import FetchWindow
from investo.sources.theblock_crypto import TheBlockCryptoAdapter
from investo.sources.yahoo_finance_news import YahooFinanceNewsAdapter
from investo.sources.yonhap_market import YonhapMarketAdapter
from investo.visuals.external_image import (
    _manifest_from_item,
    fetch_contextual_external_image,
)
from investo.visuals.policy import external_image_scraping_enabled
from tests.unit.sources._mock_transport import mock_client as _mock_client

_TARGET = date(2026, 5, 7)
_JPEG_BYTES = b"\xff\xd8\xff" + (b"\0" * 128)
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + (b"\0" * 128)


def _item(raw_metadata: dict[str, str]) -> NormalizedItem:
    return NormalizedItem(
        source_name="licensed-image-source",
        category="news",
        title="AI stocks rally",
        url="https://example.com/article",
        published_at=datetime(2026, 5, 7, 12, 0, tzinfo=UTC),
        raw_metadata=raw_metadata,
    )


def _client(content: bytes, content_type: str = "image/jpeg") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": content_type},
            content=content,
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def _metadata() -> dict[str, str]:
    return {
        "visual_image_url": "https://images.example.com/market.jpg",
        "visual_image_license": "CC BY 4.0",
        "visual_image_attribution": "Example Images / CC BY 4.0",
        "visual_image_author": "Example Images",
        "visual_image_allowed_use": "Public redistribution with attribution",
    }


def test_fetch_contextual_external_image_requires_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INVESTO_EXTERNAL_IMAGE_ASSETS", raising=False)
    result = fetch_contextual_external_image(
        (_item(_metadata()),),
        target_date=_TARGET,
        client=_client(_JPEG_BYTES),
    )

    assert result is None


def test_fetch_contextual_external_image_downloads_licensed_jpeg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ASSETS", "1")
    result = fetch_contextual_external_image(
        (_item(_metadata()),),
        target_date=_TARGET,
        client=_client(_JPEG_BYTES),
    )

    assert result is not None
    assert result.content == _JPEG_BYTES
    assert result.extension == ".jpg"
    assert result.manifest.license == "CC BY 4.0"
    assert result.source_item_title == "AI stocks rally"


def test_fetch_contextual_external_image_skips_missing_license(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = _metadata()
    metadata.pop("visual_image_license")
    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ASSETS", "1")
    result = fetch_contextual_external_image(
        (_item(metadata),),
        target_date=_TARGET,
        client=_client(_JPEG_BYTES),
    )

    assert result is None


def test_fetch_contextual_external_image_rejects_content_type_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ASSETS", "1")
    result = fetch_contextual_external_image(
        (_item(_metadata()),),
        target_date=_TARGET,
        client=_client(_PNG_BYTES, content_type="image/jpeg"),
    )

    assert result is None


# ---------------------------------------------------------------------------
# u136 Step 4 — license-key non-pollution regression (Contract #4)
# ---------------------------------------------------------------------------

_SOURCES_FIXTURES = Path(__file__).parent.parent / "sources" / "fixtures" / "api"

# Every adapter that harvests feed image metadata since u136, with the
# KST date matching its recorded fixture. If a fourth adapter ever
# gains image harvesting, it MUST be added here.
_HARVESTING_ADAPTERS = [
    pytest.param(YonhapMarketAdapter, "yonhap-market", date(2026, 7, 16), id="yonhap-market"),
    pytest.param(
        YahooFinanceNewsAdapter, "yahoo-finance-news", date(2026, 7, 16), id="yahoo-finance-news"
    ),
    pytest.param(TheBlockCryptoAdapter, "theblock-crypto", date(2026, 7, 16), id="theblock-crypto"),
]

# License-family keys (all synonyms external_image._manifest_from_item
# reads) that no adapter may ever emit into raw_metadata.
_FORBIDDEN_LICENSE_KEYS = frozenset(
    {
        "image_license",
        "image_attribution",
        "image_author",
        "image_allowed_use",
        "license",
        "attribution",
        "author",
        "allowed_use",
    }
)


async def _replay_harvested_items(
    adapter_cls: type[YonhapMarketAdapter]
    | type[YahooFinanceNewsAdapter]
    | type[TheBlockCryptoAdapter],
    fixture_dir: str,
    kst_date: date,
) -> tuple[NormalizedItem, ...]:
    """Replay one adapter against its recorded fixture (R10 — no live I/O)."""
    body = (_SOURCES_FIXTURES / fixture_dir / "feed.xml").read_bytes()
    window = FetchWindow.from_kst_date(kst_date)
    async with _mock_client(body) as client:
        items = await adapter_cls().fetch(client, window)
    assert items, f"{fixture_dir}: fixture replay yielded no items"
    assert any("image_url" in item.raw_metadata for item in items), (
        f"{fixture_dir}: expected image-bearing items in the replay — "
        "the non-pollution invariant must be exercised against harvested images"
    )
    return tuple(items)


@pytest.mark.parametrize(("adapter_cls", "fixture_dir", "kst_date"), _HARVESTING_ADAPTERS)
async def test_harvested_items_never_yield_license_manifest(
    adapter_cls: type[YonhapMarketAdapter]
    | type[YahooFinanceNewsAdapter]
    | type[TheBlockCryptoAdapter],
    fixture_dir: str,
    kst_date: date,
) -> None:
    # Contract #4 core assertion: harvested image metadata alone can
    # never satisfy the license-manifest requirement, so the dormant
    # fetch path sees None for every item.
    items = await _replay_harvested_items(adapter_cls, fixture_dir, kst_date)
    for item in items:
        assert _manifest_from_item(item, target_date=kst_date) is None


@pytest.mark.parametrize(("adapter_cls", "fixture_dir", "kst_date"), _HARVESTING_ADAPTERS)
async def test_harvested_items_carry_no_license_family_keys(
    adapter_cls: type[YonhapMarketAdapter]
    | type[YahooFinanceNewsAdapter]
    | type[TheBlockCryptoAdapter],
    fixture_dir: str,
    kst_date: date,
) -> None:
    # Consolidated emit-forbidden-keys absence across every replayed
    # raw_metadata bag: no license-family synonym, no visual_image_*
    # prefixed key at all (harvest writes plain image_* keys only).
    items = await _replay_harvested_items(adapter_cls, fixture_dir, kst_date)
    for item in items:
        keys = set(item.raw_metadata.keys())
        assert not keys & _FORBIDDEN_LICENSE_KEYS
        assert not any(key.startswith("visual_image_") for key in keys)


async def test_scraping_flag_on_harvested_items_trigger_no_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The strongest Contract #4 acceptance: even with the operator
    # opt-in env flag forced ON, fetch_contextual_external_image must
    # not perform a single HTTP request when fed only harvested items.
    # The injected client's transport fails the test on ANY request.
    monkeypatch.setenv("INVESTO_EXTERNAL_IMAGE_ASSETS", "1")
    # Sanity: the opt-in really is armed — the early-return guard in
    # fetch_contextual_external_image is NOT what keeps this dormant.
    assert external_image_scraping_enabled() is True

    all_items: list[NormalizedItem] = []
    for param in _HARVESTING_ADAPTERS:
        adapter_cls, fixture_dir, kst_date = param.values
        all_items.extend(await _replay_harvested_items(adapter_cls, fixture_dir, kst_date))

    def _fail_on_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"fetch path must stay dormant for harvested items; attempted GET {request.url}"
        )

    with httpx.Client(transport=httpx.MockTransport(_fail_on_request)) as spy_client:
        result = fetch_contextual_external_image(
            tuple(all_items),
            target_date=date(2026, 7, 16),
            client=spy_client,
        )

    assert result is None
