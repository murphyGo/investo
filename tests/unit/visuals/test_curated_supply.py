"""U-146 exact-file rights evidence and filing-graph tests."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from investo.visuals.curated import LIBRARY_ROOT, default_registry, load_library
from investo.visuals.curated_supply import (
    DECISION_FILENAME,
    EVIDENCE_FILENAME,
    LEGACY_V0_ASSET_IDS,
    LEGACY_V0_FILENAME,
    LEGACY_V0_SHA256,
    PACKET_FILENAME,
    CuratedRightsEvidence,
    CuratedSupplyError,
    LegacyCuratedSeal,
    canonical_json_bytes,
    prepare_commons_evidence,
    strict_json_load,
    validate_curated_rights_graph,
    write_pending_review_packet,
)
from tests.unit.visuals._image_bytes import make_jpeg


def _snapshot(*, structured: bool = True, license_qid: str = "Q6938433") -> dict[str, object]:
    page_id = 12345
    revision = 67890
    binary = make_jpeg(1280, 960)
    payload: dict[str, object] = {
        "capture": {
            "binary_response": {
                "content_length": len(binary),
                "etag_md5": hashlib.md5(binary, usedforsecurity=False).hexdigest(),
                "url": "https://upload.wikimedia.org/example-thumb.jpg",
            }
        },
        "imageinfo_response": {
            "query": {
                "pages": [
                    {
                        "pageid": page_id,
                        "title": "File:Example data center.jpg",
                        "revisions": [{"revid": revision}],
                        "imageinfo": [
                            {
                                "timestamp": "2026-08-03T00:00:00Z",
                                "width": 1280,
                                "height": 960,
                                "thumbwidth": 1280,
                                "thumbheight": 960,
                                "mime": "image/jpeg",
                                "sha1": "a" * 40,
                                "url": "https://upload.wikimedia.org/example-original.jpg",
                                "thumburl": "https://upload.wikimedia.org/example-thumb.jpg",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC0"},
                                    "LicenseUrl": {
                                        "value": "https://creativecommons.org/publicdomain/zero/1.0/"
                                    },
                                    "Artist": {"value": "Example Author"},
                                    "Copyrighted": {"value": "True"},
                                    "Restrictions": {"value": ""},
                                    "Categories": {"value": "CC-Zero|Data centers"},
                                },
                            }
                        ],
                    }
                ]
            }
        },
    }
    if structured:
        payload["structured_data_response"] = {
            "entities": {
                f"M{page_id}": {
                    "lastrevid": revision,
                    "statements": {
                        "P275": [
                            {
                                "rank": "normal",
                                "mainsnak": {
                                    "snaktype": "value",
                                    "datavalue": {"value": {"id": license_qid}},
                                },
                            }
                        ],
                        "P6216": [
                            {
                                "rank": "normal",
                                "mainsnak": {
                                    "snaktype": "value",
                                    "datavalue": {"value": {"id": "Q88088423"}},
                                },
                            }
                        ],
                    },
                }
            }
        }
    return payload


def _write_inputs(
    tmp_path: Path, *, snapshot: dict[str, object] | None = None
) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        json.dumps(snapshot or _snapshot(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    binary_path = tmp_path / "candidate.jpg"
    binary_path.write_bytes(make_jpeg(1280, 960))
    return snapshot_path, binary_path


def _evidence(
    tmp_path: Path, *, snapshot: dict[str, object] | None = None
) -> CuratedRightsEvidence:
    snapshot_path, binary_path = _write_inputs(tmp_path, snapshot=snapshot)
    return prepare_commons_evidence(
        asset_id="data-center-example",
        category="topic",
        expected_title="File:Example data center.jpg",
        snapshot_path=snapshot_path,
        binary_path=binary_path,
        verified_on=date(2026, 8, 3),
    )


def test_commons_cc0_with_matching_structured_data_is_ready_not_approved(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path)
    assert evidence.assessment == "READY_FOR_REVIEW"
    assert evidence.manifest_license == "cc0"
    assert evidence.structured_license_ids == ("Q6938433",)
    assert not (tmp_path / DECISION_FILENAME).exists()


def test_missing_structured_license_blocks_metadata_only(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path, snapshot=_snapshot(structured=False))
    assert evidence.assessment == "BLOCKED"
    assert "SOURCE_POLICY_METADATA_ONLY" in evidence.blocker_codes


def test_structured_license_contradiction_blocks(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path, snapshot=_snapshot(license_qid="Q18199165"))
    assert evidence.assessment == "BLOCKED"
    assert "LICENSE_CONTRADICTION" in evidence.blocker_codes


def test_original_binary_must_match_commons_sha1(tmp_path: Path) -> None:
    snapshot_path, binary_path = _write_inputs(tmp_path)
    evidence = prepare_commons_evidence(
        asset_id="data-center-example",
        category="topic",
        expected_title="File:Example data center.jpg",
        snapshot_path=snapshot_path,
        binary_path=binary_path,
        verified_on=date(2026, 8, 3),
        variant_kind="original",
    )
    assert evidence.assessment == "BLOCKED"
    assert "BINARY_MISMATCH" in evidence.blocker_codes


def test_thumbnail_binary_must_match_provider_etag(tmp_path: Path) -> None:
    snapshot = _snapshot()
    capture = snapshot["capture"]
    assert isinstance(capture, dict)
    capture["binary_response"]["etag_md5"] = "0" * 32  # type: ignore[index]
    evidence = _evidence(tmp_path, snapshot=snapshot)
    assert evidence.assessment == "BLOCKED"
    assert "BINARY_MISMATCH" in evidence.blocker_codes


def test_deprecated_only_structured_license_does_not_clear(tmp_path: Path) -> None:
    snapshot = _snapshot()
    structured = snapshot["structured_data_response"]
    assert isinstance(structured, dict)
    entity = structured["entities"]["M12345"]  # type: ignore[index]
    for statements in entity["statements"].values():
        for statement in statements:
            statement["rank"] = "deprecated"
    evidence = _evidence(tmp_path, snapshot=snapshot)
    assert evidence.assessment == "BLOCKED"
    assert "SOURCE_POLICY_METADATA_ONLY" in evidence.blocker_codes


def test_unranked_structured_license_does_not_clear(tmp_path: Path) -> None:
    snapshot = _snapshot()
    structured = snapshot["structured_data_response"]
    assert isinstance(structured, dict)
    entity = structured["entities"]["M12345"]  # type: ignore[index]
    for statements in entity["statements"].values():
        for statement in statements:
            statement.pop("rank")
    evidence = _evidence(tmp_path, snapshot=snapshot)
    assert evidence.assessment == "BLOCKED"
    assert "SOURCE_POLICY_METADATA_ONLY" in evidence.blocker_codes


def test_secret_shaped_source_metadata_fails_closed(tmp_path: Path) -> None:
    snapshot = _snapshot()
    imageinfo = snapshot["imageinfo_response"]
    assert isinstance(imageinfo, dict)
    pages = imageinfo["query"]["pages"]  # type: ignore[index]
    pages[0]["imageinfo"][0]["thumburl"] = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/"
        "OxidizedSiliconWafer.jpg/1280px-OxidizedSiliconWafer.jpg"
    )
    with pytest.raises(CuratedSupplyError, match="secret-shaped"):
        _evidence(tmp_path, snapshot=snapshot)


def test_unused_snapshot_secret_fails_closed(tmp_path: Path) -> None:
    snapshot = _snapshot()
    snapshot["unused"] = "123456789:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQR"
    with pytest.raises(CuratedSupplyError, match="secret-shaped"):
        _evidence(tmp_path, snapshot=snapshot)


@pytest.mark.parametrize(
    "public_url",
    (
        "https://commons.wikimedia.org/w/api.php?"
        "action=query&titles=123456789:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQR",
        "https://upload.wikimedia.org/wikipedia/commons/"
        "123456789:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQR/example.jpg",
    ),
)
def test_allowlisted_public_url_cannot_hide_secret(tmp_path: Path, public_url: str) -> None:
    snapshot = _snapshot()
    snapshot["unused_public_url"] = public_url
    with pytest.raises(CuratedSupplyError, match="secret-shaped"):
        _evidence(tmp_path, snapshot=snapshot)


@pytest.mark.parametrize("encode_count", (1, 2))
def test_allowlisted_public_url_cannot_hide_percent_encoded_secret(
    tmp_path: Path, encode_count: int
) -> None:
    secret = "123456789:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQR"
    encoded = "".join(f"%{byte:02X}" for byte in secret.encode())
    for _iteration in range(encode_count - 1):
        encoded = encoded.replace("%", "%25")
    snapshot = _snapshot()
    snapshot["unused_public_url"] = (
        f"https://upload.wikimedia.org/wikipedia/commons/{encoded}/example.jpg"
    )
    with pytest.raises(CuratedSupplyError, match="secret-shaped"):
        _evidence(tmp_path, snapshot=snapshot)


def test_ready_model_is_frozen_and_forbids_extra() -> None:
    with pytest.raises(ValidationError):
        CuratedRightsEvidence.model_validate({"unexpected": True})


def test_strict_json_rejects_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    with pytest.raises(CuratedSupplyError, match="duplicate"):
        strict_json_load(path)


def test_review_packet_is_deterministic_and_never_approves(tmp_path: Path) -> None:
    snapshot_path, binary_path = _write_inputs(tmp_path)
    evidence = prepare_commons_evidence(
        asset_id="data-center-example",
        category="topic",
        expected_title="File:Example data center.jpg",
        snapshot_path=snapshot_path,
        binary_path=binary_path,
        verified_on=date(2026, 8, 3),
    )
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    first = write_pending_review_packet(
        evidence=evidence,
        snapshot_path=snapshot_path,
        binary_path=binary_path,
        output_dir=tmp_path / "packet-a",
        repo_root=repo_root,
    )
    second = write_pending_review_packet(
        evidence=evidence,
        snapshot_path=snapshot_path,
        binary_path=binary_path,
        output_dir=tmp_path / "packet-b",
        repo_root=repo_root,
    )
    assert (first / EVIDENCE_FILENAME).read_bytes() == (second / EVIDENCE_FILENAME).read_bytes()
    assert (first / PACKET_FILENAME).read_bytes() == (second / PACKET_FILENAME).read_bytes()
    assert not (first / DECISION_FILENAME).exists()
    assert not tuple(first.glob("*.manifest.json"))


def test_review_packet_refuses_repository_output(tmp_path: Path) -> None:
    snapshot_path, binary_path = _write_inputs(tmp_path)
    evidence = _evidence(tmp_path / "second")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    with pytest.raises(CuratedSupplyError, match="outside the repository"):
        write_pending_review_packet(
            evidence=evidence,
            snapshot_path=snapshot_path,
            binary_path=binary_path,
            output_dir=repo_root / "assets" / "library" / "pending",
            repo_root=repo_root,
        )


def test_review_packet_rejects_input_changed_after_evidence(tmp_path: Path) -> None:
    snapshot_path, binary_path = _write_inputs(tmp_path)
    evidence = prepare_commons_evidence(
        asset_id="data-center-example",
        category="topic",
        expected_title="File:Example data center.jpg",
        snapshot_path=snapshot_path,
        binary_path=binary_path,
        verified_on=date(2026, 8, 3),
    )
    binary_path.write_bytes(binary_path.read_bytes() + b"changed")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    with pytest.raises(CuratedSupplyError, match="binary changed"):
        write_pending_review_packet(
            evidence=evidence,
            snapshot_path=snapshot_path,
            binary_path=binary_path,
            output_dir=tmp_path / "stale-packet",
            repo_root=repo_root,
        )


def test_legacy_v0_exact_15_entries_and_sealed_digest() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / LIBRARY_ROOT / "_rights" / LEGACY_V0_FILENAME
    assert hashlib.sha256(path.read_bytes()).hexdigest() == LEGACY_V0_SHA256
    seal = LegacyCuratedSeal.model_validate(strict_json_load(path))
    assert {entry.asset_id for entry in seal.entries} == LEGACY_V0_ASSET_IDS
    assert len(seal.entries) == 15


def test_current_library_rights_graph_is_green() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    root = repo_root / LIBRARY_ROOT
    library = load_library(root)
    report = validate_curated_rights_graph(
        library_root=root,
        library=library,
        registry=default_registry(),
    )
    assert report.legacy_assets == 15
    assert report.evidence_backed_assets == 4


def test_legacy_binary_tamper_fails(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    source = repo_root / LIBRARY_ROOT
    copied = tmp_path / "library"
    shutil.copytree(source, copied)
    bitcoin = copied / "asset" / "bitcoin.jpg"
    bitcoin.write_bytes(bitcoin.read_bytes() + b"tamper")
    library = load_library(copied)
    with pytest.raises(CuratedSupplyError, match="legacy binary digest"):
        validate_curated_rights_graph(
            library_root=copied,
            library=library,
            registry=default_registry(),
        )


def test_missing_legacy_asset_cannot_shrink_the_seal(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    copied = tmp_path / "library"
    shutil.copytree(repo_root / LIBRARY_ROOT, copied)
    (copied / "asset" / "bitcoin.jpg").unlink()
    (copied / "asset" / "bitcoin.manifest.json").unlink()
    library = load_library(copied)
    registry = tuple(entry for entry in default_registry() if "bitcoin" not in entry.asset_ids)
    with pytest.raises(CuratedSupplyError, match="not all present"):
        validate_curated_rights_graph(
            library_root=copied,
            library=library,
            registry=registry,
        )


def test_evidence_whitespace_change_breaks_approved_decision(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    copied = tmp_path / "library"
    shutil.copytree(repo_root / LIBRARY_ROOT, copied)
    evidence = copied / "_rights" / "data-center-roof" / EVIDENCE_FILENAME
    evidence.write_bytes(evidence.read_bytes() + b"\n")
    library = load_library(copied)
    with pytest.raises(CuratedSupplyError, match="evidence digest"):
        validate_curated_rights_graph(
            library_root=copied,
            library=library,
            registry=default_registry(),
        )


def test_missing_new_filing_decision_fails_closed(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    copied = tmp_path / "library"
    shutil.copytree(repo_root / LIBRARY_ROOT, copied)
    decision = copied / "_rights" / "gold-bullion" / DECISION_FILENAME
    decision.unlink()
    library = load_library(copied)
    with pytest.raises(CuratedSupplyError, match="rights JSON is unreadable"):
        validate_curated_rights_graph(
            library_root=copied,
            library=library,
            registry=default_registry(),
        )


def test_orphan_rights_directory_fails_closed(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    copied = tmp_path / "library"
    shutil.copytree(repo_root / LIBRARY_ROOT, copied)
    (copied / "_rights" / "orphan-review").mkdir()
    library = load_library(copied)
    with pytest.raises(CuratedSupplyError, match="rights artifacts"):
        validate_curated_rights_graph(
            library_root=copied,
            library=library,
            registry=default_registry(),
        )


def test_extra_file_inside_rights_directory_fails_closed(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    copied = tmp_path / "library"
    shutil.copytree(repo_root / LIBRARY_ROOT, copied)
    (copied / "_rights" / "gold-bullion" / "unreviewed.txt").write_text(
        "unexpected", encoding="utf-8"
    )
    library = load_library(copied)
    with pytest.raises(CuratedSupplyError, match="directory shape"):
        validate_curated_rights_graph(
            library_root=copied,
            library=library,
            registry=default_registry(),
        )


def test_symlink_inside_rights_directory_fails_closed(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    copied = tmp_path / "library"
    shutil.copytree(repo_root / LIBRARY_ROOT, copied)
    evidence = copied / "_rights" / "gold-bullion" / EVIDENCE_FILENAME
    target = tmp_path / "external-evidence.json"
    shutil.copyfile(evidence, target)
    evidence.unlink()
    evidence.symlink_to(target)
    library = load_library(copied)
    with pytest.raises(CuratedSupplyError, match="symbolic link"):
        validate_curated_rights_graph(
            library_root=copied,
            library=library,
            registry=default_registry(),
        )


def test_canonical_evidence_bytes_are_stable(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path)
    assert canonical_json_bytes(evidence) == canonical_json_bytes(evidence)
