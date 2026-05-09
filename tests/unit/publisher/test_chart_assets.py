"""Static asset invariant tests for u50 lightweight-charts-embed.

These tests pin three things:

1. The Lightweight Charts UMD bundle exists at the path referenced by
   ``mkdocs.yml`` ``extra_javascript`` and lies in the expected size
   band (~50KB-200KB; the v4.x bundle is ~160KB minified).
2. The bundle's sha256 matches the recorded value, so an accidental
   replacement (e.g. a future "auto-update" PR) fails this test
   loudly. Updating the bundle requires updating this constant.
3. The Apache-2.0 LICENSE.txt sibling exists, has a sha256 invariant,
   and starts with the canonical Apache header. The plan originally
   said "MIT"; the upstream repo (TradingView/lightweight-charts) is
   actually Apache-2.0 — both are OSI-approved permissive licenses
   that allow self-hosted redistribution.
4. The init script (``investo-chart-init.js``) exists and references
   the global ``LightweightCharts`` constructor.
5. ``mkdocs.yml`` registers both files under ``extra_javascript`` (the
   string-grep keeps the test independent of yaml parsing).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = REPO_ROOT / "site_docs" / "assets"
BUNDLE_PATH = ASSETS_DIR / "lightweight-charts.standalone.production.js"
LICENSE_PATH = ASSETS_DIR / "lightweight-charts.LICENSE.txt"
INIT_PATH = ASSETS_DIR / "investo-chart-init.js"
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"


# Pinned at vendor time. To update the bundle: download the new
# release UMD build, paste the new sha256 here, update this docstring
# with the new version tag, and run the suite. Lightweight Charts
# v4.2.3 (Apache-2.0) — released 2026-04-23.
EXPECTED_BUNDLE_SHA256 = "c7dda807d662a95b3d257119ed315cec669e3bdf5aaece75c480a39307f23540"
EXPECTED_LICENSE_SHA256 = "70c9d5382506dd184465425c08a99ad9bd6d9ac1313c252968ba0b585e5ef823"

# Reasonable size band. v4.2.3 is 163,684 bytes; the band tolerates
# minor minifier variation in future bumps without forcing a re-pin
# every release.
BUNDLE_MIN_BYTES = 50_000
BUNDLE_MAX_BYTES = 250_000


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_bundle_exists() -> None:
    assert BUNDLE_PATH.is_file(), f"missing bundle: {BUNDLE_PATH}"


def test_bundle_size_in_band() -> None:
    size = BUNDLE_PATH.stat().st_size
    assert BUNDLE_MIN_BYTES <= size <= BUNDLE_MAX_BYTES, (
        f"unexpected bundle size: {size} bytes (band {BUNDLE_MIN_BYTES}-{BUNDLE_MAX_BYTES})"
    )


def test_bundle_sha256_pinned() -> None:
    actual = _sha256(BUNDLE_PATH)
    assert actual == EXPECTED_BUNDLE_SHA256, (
        f"bundle sha256 changed; expected {EXPECTED_BUNDLE_SHA256}, got {actual}. "
        "Intentional update? Bump EXPECTED_BUNDLE_SHA256 in this test."
    )


def test_bundle_exposes_global_constructor() -> None:
    text = BUNDLE_PATH.read_text(encoding="utf-8")
    assert "LightweightCharts" in text, "bundle does not expose the LightweightCharts global"


def test_license_exists_and_pinned() -> None:
    assert LICENSE_PATH.is_file(), f"missing LICENSE: {LICENSE_PATH}"
    actual = _sha256(LICENSE_PATH)
    assert actual == EXPECTED_LICENSE_SHA256, (
        "LICENSE sha256 changed; bundle and license must update together."
    )


def test_license_is_apache_2_0_header() -> None:
    head = LICENSE_PATH.read_text(encoding="utf-8")[:600]
    assert "Apache License" in head
    assert "Version 2.0" in head


def test_init_script_exists_and_references_global() -> None:
    assert INIT_PATH.is_file(), f"missing init script: {INIT_PATH}"
    text = INIT_PATH.read_text(encoding="utf-8")
    assert "LightweightCharts" in text
    assert "investo-chart" in text


def test_mkdocs_yml_registers_both_extra_javascript_paths() -> None:
    text = MKDOCS_YML.read_text(encoding="utf-8")
    assert "extra_javascript:" in text
    assert "assets/lightweight-charts.standalone.production.js" in text
    assert "assets/investo-chart-init.js" in text


@pytest.mark.parametrize(
    "needle",
    [
        "data-history",
        "data-ticker",
        "investo-chart",
    ],
)
def test_init_script_consumes_publisher_emitted_attributes(needle: str) -> None:
    """Pin: the JS init layer reads the same attributes the publisher writes."""
    text = INIT_PATH.read_text(encoding="utf-8")
    assert needle in text
