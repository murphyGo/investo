"""Tests for ``investo.visuals.image_library`` (u137 Steps 1-2).

Step 1 pins FD Contract #1 / E1 / R2-R4 / I1-I4 for the candidate
ledger: identity normalization (I1), sanitize + caps (I2/R4),
target-date provenance (I3), byte-determinism + merge-rewrite
idempotency with existing-row-wins (I4/R3), imageless skip + same-run
first-wins dedup (R3), atomic-write convention, and R13 (AC-1.3) —
including the fail-closed URL screening documented in the module
docstring.

Step 2 pins Contract #2/#3 read-side / E2/E5 / R5-R7 / I5-I9/I14 for
the recurrence index: distinct-ledger-date ``seen_count`` (AC-137.6),
rights mirroring from operator clearance files (blocked-wins, I9
URL-identity, fail-closed manifest parsing), atomic + deterministic
rewrite, and the no-auto-promotion guarantee.

All filesystem writes go to ``tmp_path`` — never the real ``archive/``.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo.models import NormalizedItem
from investo.visuals.image_library import (
    ImageCandidateRecord,
    append_candidates,
    candidate_id_for_url,
    clearances_dir_for,
    index_path_for,
    ledger_path_for,
    normalize_image_url,
    update_index,
)
from investo.visuals.policy import ExternalAssetManifest

_TARGET = date(2026, 7, 16)
_PUBLISHED = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def _item(
    *,
    source_name: str = "yonhap-market",
    title: str = "뉴욕증시, 반도체주 약세에 하락 출발",
    url: str | None = "https://www.yna.co.kr/view/AKR001",
    image_url: str | None = "https://img.yna.co.kr/photo/reuters/2026/07/16/PRU001_P2.jpg",
    extra_metadata: dict[str, str | int] | None = None,
) -> NormalizedItem:
    raw_metadata: dict[str, str | int] = {}
    if image_url is not None:
        raw_metadata["image_url"] = image_url
    if extra_metadata:
        raw_metadata.update(extra_metadata)
    return NormalizedItem(
        source_name=source_name,
        category="news",
        title=title,
        url=url,
        published_at=_PUBLISHED,
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# I1 / R2 — URL normalization + candidate identity
# ---------------------------------------------------------------------------


def test_normalize_lowercases_scheme_and_host_and_strips_fragment() -> None:
    assert (
        normalize_image_url("HTTPS://IMG.Example.COM/Photo/A.jpg#section")
        == "https://img.example.com/Photo/A.jpg"
    )


def test_normalize_preserves_path_query_port_byte_exact() -> None:
    # Path case, query order/case, and port survive untouched (R2: no
    # further canonicalization in v1).
    url = "https://cdn.example.com:8080/A/B.jpg?B=2&a=1"
    assert normalize_image_url(url) == url


def test_candidate_id_is_case_and_fragment_insensitive() -> None:
    a = candidate_id_for_url("https://img.example.com/a.jpg")
    b = candidate_id_for_url("HTTPS://IMG.EXAMPLE.COM/a.jpg#frag")
    assert a == b
    assert len(a) == 64
    assert a == a.lower()


def test_candidate_id_distinguishes_path_case_and_query() -> None:
    base = candidate_id_for_url("https://img.example.com/a.jpg")
    assert candidate_id_for_url("https://img.example.com/A.jpg") != base
    assert candidate_id_for_url("https://img.example.com/a.jpg?w=1") != base


def test_record_rejects_mismatched_candidate_id() -> None:
    # I1 self-verification: a row whose id does not hash-match its URL
    # cannot be constructed (nor parsed back during merge).
    with pytest.raises(ValueError, match="does not match"):
        ImageCandidateRecord(
            candidate_id="0" * 64,
            image_url="https://img.example.com/a.jpg",
            source_name="yonhap-market",
            segment="domestic-equity",
            item_url="https://www.yna.co.kr/view/x",
            item_title="제목",
            collected_on=_TARGET,
        )


# ---------------------------------------------------------------------------
# Ledger write — happy path + determinism (I4)
# ---------------------------------------------------------------------------


def test_append_writes_sorted_jsonl_with_expected_fields(tmp_path: Path) -> None:
    items = {
        "domestic-equity": [
            _item(
                image_url="https://img.yna.co.kr/b.jpg", extra_metadata={"image_mime": "image/jpeg"}
            ),
        ],
        "crypto": [
            _item(
                source_name="theblock-crypto",
                title="BTC rallies",
                url="https://www.theblock.co/post/1",
                image_url="https://www.tbstat.com/a.jpg",
                extra_metadata={"image_width": 800, "image_height": 450},
            ),
        ],
    }
    report = append_candidates(_TARGET, items, ledger_root=tmp_path)

    path = ledger_path_for(_TARGET, ledger_root=tmp_path)
    assert report.ledger_path == path
    assert path == tmp_path / "2026" / "2026-07-16.jsonl"
    assert report.items_seen == 2
    assert report.candidates_written == 2
    assert report.existing_preserved == 0

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    rows = [ImageCandidateRecord.model_validate_json(line) for line in lines]
    # candidate_id-lexical row order (I4).
    assert [r.candidate_id for r in rows] == sorted(r.candidate_id for r in rows)
    by_source = {r.source_name: r for r in rows}
    tb = by_source["theblock-crypto"]
    assert tb.segment == "crypto"
    assert tb.image_width == 800
    assert tb.image_height == 450
    assert tb.image_mime is None
    assert tb.collected_on == _TARGET
    yna = by_source["yonhap-market"]
    assert yna.segment == "domestic-equity"
    assert yna.image_mime == "image/jpeg"
    assert yna.image_width is None


def test_same_input_twice_is_byte_identical(tmp_path: Path) -> None:
    items = {
        "us-equity": [
            _item(
                source_name="yahoo-finance-news",
                url="https://finance.yahoo.com/news/a.html",
                image_url="https://media.zenfs.com/en/reuters.com/abc",
                extra_metadata={"image_width": 130, "image_height": 86},
            ),
            _item(image_url="https://img.yna.co.kr/z.jpg"),
        ],
    }
    path = ledger_path_for(_TARGET, ledger_root=tmp_path)

    first_report = append_candidates(_TARGET, items, ledger_root=tmp_path)
    first_bytes = path.read_bytes()
    second_report = append_candidates(_TARGET, items, ledger_root=tmp_path)

    assert path.read_bytes() == first_bytes  # I4 byte-idempotent
    assert first_report.candidates_written == 2
    assert second_report.candidates_written == 0
    assert second_report.existing_preserved == 2


def test_merge_rewrite_preserves_existing_rows_and_existing_wins(tmp_path: Path) -> None:
    image_url = "https://img.yna.co.kr/conflict.jpg"
    first = {"domestic-equity": [_item(title="원래 제목", image_url=image_url)]}
    append_candidates(_TARGET, first, ledger_root=tmp_path)
    path = ledger_path_for(_TARGET, ledger_root=tmp_path)
    original_line = path.read_text(encoding="utf-8")

    # Later run: same candidate with a different title (existing row must
    # win, byte-exact) + one genuinely new candidate (must be added).
    second = {
        "domestic-equity": [
            _item(title="바뀐 제목", image_url=image_url),
            _item(title="새 기사", image_url="https://img.yna.co.kr/new.jpg"),
        ],
    }
    report = append_candidates(_TARGET, second, ledger_root=tmp_path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert original_line.rstrip("\n") in lines  # earlier row byte-preserved
    titles = {ImageCandidateRecord.model_validate_json(line).item_title for line in lines}
    assert titles == {"원래 제목", "새 기사"}  # existing-row-wins
    assert report.candidates_written == 1
    assert report.existing_preserved == 1


def test_empty_merge_writes_no_file(tmp_path: Path) -> None:
    report = append_candidates(
        _TARGET, {"domestic-equity": [_item(image_url=None)]}, ledger_root=tmp_path
    )
    assert not report.ledger_path.exists()
    assert report.imageless_skipped == 1
    assert report.candidates_written == 0


# ---------------------------------------------------------------------------
# R3 — imageless skip + same-run first-wins dedup
# ---------------------------------------------------------------------------


def test_imageless_items_are_skipped(tmp_path: Path) -> None:
    items = {
        "domestic-equity": [
            _item(image_url=None),
            _item(image_url="https://img.yna.co.kr/only.jpg"),
        ],
    }
    report = append_candidates(_TARGET, items, ledger_root=tmp_path)
    assert report.items_seen == 2
    assert report.imageless_skipped == 1
    assert report.candidates_written == 1


def test_same_run_duplicate_candidate_first_wins(tmp_path: Path) -> None:
    # Same image URL (case-varied host → same candidate_id) on two items
    # — the first in routed order wins; later ones count as duplicates.
    items = {
        "domestic-equity": [
            _item(title="첫 기사", image_url="https://img.yna.co.kr/dup.jpg"),
            _item(title="둘째 기사", image_url="https://IMG.YNA.CO.KR/dup.jpg"),
        ],
    }
    report = append_candidates(_TARGET, items, ledger_root=tmp_path)
    assert report.duplicates_skipped == 1
    lines = report.ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert ImageCandidateRecord.model_validate_json(lines[0]).item_title == "첫 기사"


# ---------------------------------------------------------------------------
# I2 / R4 — title sanitize + cap; AC-1.3 R13 pinned test
# ---------------------------------------------------------------------------


def test_item_title_is_capped_at_160_after_sanitize(tmp_path: Path) -> None:
    long_title = "가" * 400
    items = {"domestic-equity": [_item(title=long_title)]}
    report = append_candidates(_TARGET, items, ledger_root=tmp_path)
    row = ImageCandidateRecord.model_validate_json(
        report.ledger_path.read_text(encoding="utf-8").splitlines()[0]
    )
    assert row.item_title == "가" * 160


def test_secret_shaped_title_is_redacted_in_persisted_row(tmp_path: Path) -> None:
    # AC-1.3 pinned test: a Telegram-bot-token-shaped value in the
    # carrying item's title never lands in the ledger.
    token = "8123456789:AAF-abcdefghijklmnopqrstuvwxyz123456789"
    items = {"domestic-equity": [_item(title=f"제목 {token} 끝")]}
    report = append_candidates(_TARGET, items, ledger_root=tmp_path)

    content = report.ledger_path.read_text(encoding="utf-8")
    assert token not in content
    assert "[REDACTED_BOT_TOKEN]" in content


def test_env_secret_value_never_persisted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # R13: a live env secret appearing in free text is scrubbed by the
    # chokepoint before the row is written.
    secret = "super-secret-operator-token-value-1234"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", secret)
    items = {"domestic-equity": [_item(title=f"유출 {secret} 사고")]}
    report = append_candidates(_TARGET, items, ledger_root=tmp_path)
    content = report.ledger_path.read_text(encoding="utf-8")
    assert secret not in content


def test_image_credit_is_sanitized_and_capped(tmp_path: Path) -> None:
    # Realistic over-long credit (Korean outlet text — a bare 400-char
    # alnum run would itself be redacted by the STRICT long-base64
    # pattern, which is correct chokepoint behavior but not this test's
    # subject). 4-char unit x 80 = 320 chars → capped to 240.
    long_credit = "로이터 " * 80
    items = {
        "us-equity": [
            _item(
                source_name="yahoo-finance-news",
                url="https://finance.yahoo.com/news/a.html",
                image_url="https://media.zenfs.com/en/x",
                extra_metadata={"image_credit": long_credit},
            ),
        ],
    }
    report = append_candidates(_TARGET, items, ledger_root=tmp_path)
    row = ImageCandidateRecord.model_validate_json(
        report.ledger_path.read_text(encoding="utf-8").splitlines()[0]
    )
    assert row.image_credit == long_credit[:240]
    assert row.image_credit is not None
    assert len(row.image_credit) == 240


# ---------------------------------------------------------------------------
# R13 fail-closed URL screening (module-docstring divergence contract)
# ---------------------------------------------------------------------------


def test_url_carrying_env_secret_drops_candidate_entirely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # URLs are never partially redacted (that would break I1 identity);
    # a secret-bearing URL drops the whole candidate, fail-closed.
    secret = "svc-key-abcdef123456"
    monkeypatch.setenv("INVESTO_KRX_SERVICE_KEY", secret)
    items = {
        "domestic-equity": [
            _item(image_url=f"https://img.example.com/pic.jpg?key={secret}"),
        ],
    }
    report = append_candidates(_TARGET, items, ledger_root=tmp_path)
    assert report.screened_skipped == 1
    assert report.candidates_written == 0
    assert not report.ledger_path.exists()


def test_real_feed_shaped_urls_pass_screening(tmp_path: Path) -> None:
    # The three real recorded CDN shapes (long path runs, extension-less
    # hashes) must NOT be screened out — the leak scanner's URL-context
    # filtering keeps them.
    items = {
        "us-equity": [
            _item(
                source_name="yahoo-finance-news",
                url="https://finance.yahoo.com/news/a.html",
                image_url=(
                    "https://s.yimg.com/uu/api/res/1.2/_X3HUYULjVZnrNbZyowsfw--~B/"
                    "aD00NzQzO3c9NzExMTthcHBpZD15dGFjaHlvbg--/photo"
                ),
            ),
        ],
        "domestic-equity": [
            _item(
                image_url="https://img.yna.co.kr/photo/reuters/2026/07/16/PRU20260716306401009_P2.jpg"
            ),
        ],
    }
    report = append_candidates(_TARGET, items, ledger_root=tmp_path)
    assert report.screened_skipped == 0
    assert report.candidates_written == 2


def test_item_without_article_url_is_screened_out(tmp_path: Path) -> None:
    items = {"domestic-equity": [_item(url=None)]}
    report = append_candidates(_TARGET, items, ledger_root=tmp_path)
    assert report.screened_skipped == 1
    assert not report.ledger_path.exists()


# ---------------------------------------------------------------------------
# I3 — target-date provenance (no wall clock)
# ---------------------------------------------------------------------------


def test_collected_on_is_the_target_date_not_today(tmp_path: Path) -> None:
    past = date(2024, 1, 2)
    report = append_candidates(past, {"domestic-equity": [_item()]}, ledger_root=tmp_path)
    assert report.ledger_path == tmp_path / "2024" / "2024-01-02.jsonl"
    row = ImageCandidateRecord.model_validate_json(
        report.ledger_path.read_text(encoding="utf-8").splitlines()[0]
    )
    assert row.collected_on == past


# ---------------------------------------------------------------------------
# Atomic-write convention + corrupted existing rows
# ---------------------------------------------------------------------------


def test_no_tmp_sibling_left_after_write(tmp_path: Path) -> None:
    append_candidates(_TARGET, {"domestic-equity": [_item()]}, ledger_root=tmp_path)
    leftovers = list(tmp_path.rglob("*.tmp"))
    assert leftovers == []


def test_corrupted_existing_line_dropped_with_count(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # A hand-mangled line cannot merge deterministically: it is dropped
    # with a WARNING and surfaced in the report; valid rows still merge.
    first = {"domestic-equity": [_item(image_url="https://img.yna.co.kr/keep.jpg")]}
    append_candidates(_TARGET, first, ledger_root=tmp_path)
    path = ledger_path_for(_TARGET, ledger_root=tmp_path)
    path.write_text(path.read_text(encoding="utf-8") + "{not valid json\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="investo.visuals.image_library"):
        report = append_candidates(
            _TARGET,
            {"domestic-equity": [_item(image_url="https://img.yna.co.kr/new.jpg")]},
            ledger_root=tmp_path,
        )

    assert report.invalid_existing_dropped == 1
    assert "unparseable" in caplog.text
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2  # kept row + new row; corrupt line gone
    for line in lines:
        ImageCandidateRecord.model_validate_json(line)  # all valid again


# ---------------------------------------------------------------------------
# Step 2 — recurrence index (E2, R5, I5/I6) + rights mirror (E5, R6/R7, I7-I9)
# ---------------------------------------------------------------------------

_URL_A = "https://img.yna.co.kr/photo/reuters/recurring.jpg"
_URL_B = "https://www.tbstat.com/wp/uploads/one-off.jpg"


def _build_three_day_ledgers(root: Path) -> None:
    """Candidate A on 3 distinct dates (two sources), B on one date."""

    append_candidates(
        date(2026, 7, 14),
        {"domestic-equity": [_item(image_url=_URL_A)]},
        ledger_root=root,
    )
    append_candidates(
        date(2026, 7, 15),
        {
            "us-equity": [
                _item(
                    source_name="yahoo-finance-news",
                    url="https://finance.yahoo.com/news/a.html",
                    image_url=_URL_A,
                ),
            ],
            "crypto": [
                _item(
                    source_name="theblock-crypto",
                    url="https://www.theblock.co/post/1",
                    image_url=_URL_B,
                ),
            ],
        },
        ledger_root=root,
    )
    append_candidates(
        date(2026, 7, 16),
        {"domestic-equity": [_item(image_url=_URL_A)]},
        ledger_root=root,
    )


def _write_clearance(
    root: Path,
    image_url: str,
    *,
    kind: str = "explicit-license",
    source_url: str | None = None,
) -> str:
    """Author an operator clearance manifest; returns the candidate id."""

    cid = candidate_id_for_url(image_url)
    manifest = ExternalAssetManifest(
        kind=kind,  # type: ignore[arg-type]
        source_url=source_url or image_url,  # type: ignore[arg-type]
        license="CC BY 4.0",
        attribution="Example Agency / CC BY 4.0",
        author="Example Agency",
        fetched_on=date(2026, 7, 16),
        allowed_use="Public redistribution with attribution",
    )
    path = clearances_dir_for(ledger_root=root) / f"{cid}.manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(), encoding="utf-8")
    return cid


def _load_index(root: Path) -> dict[str, dict[str, object]]:
    loaded: dict[str, dict[str, object]] = json.loads(
        index_path_for(ledger_root=root).read_text(encoding="utf-8")
    )
    return loaded


def test_index_recurrence_counts_distinct_ledger_dates(tmp_path: Path) -> None:
    # R5 / AC-137.6 — seen_count counts distinct dates, first/last span
    # them, sources are the sorted union across appearances.
    _build_three_day_ledgers(tmp_path)
    report = update_index(date(2026, 7, 16), ledger_root=tmp_path)

    assert report.ledger_dates_scanned == 3
    assert report.candidates_indexed == 2
    index = _load_index(tmp_path)
    a = index[candidate_id_for_url(_URL_A)]
    assert a["first_seen"] == "2026-07-14"
    assert a["last_seen"] == "2026-07-16"
    assert a["seen_count"] == 3
    assert a["sources"] == ["yahoo-finance-news", "yonhap-market"]
    assert a["rights_state"] == "metadata-only"
    b = index[candidate_id_for_url(_URL_B)]
    assert b["seen_count"] == 1
    assert b["first_seen"] == b["last_seen"] == "2026-07-15"
    assert b["sources"] == ["theblock-crypto"]


def test_index_rewrite_is_byte_deterministic(tmp_path: Path) -> None:
    # I5/I6 — full derived rebuild; re-run over the same inputs is
    # byte-identical, keys candidate_id-sorted.
    _build_three_day_ledgers(tmp_path)
    update_index(date(2026, 7, 16), ledger_root=tmp_path)
    first = index_path_for(ledger_root=tmp_path).read_bytes()
    update_index(date(2026, 7, 16), ledger_root=tmp_path)
    assert index_path_for(ledger_root=tmp_path).read_bytes() == first
    index = _load_index(tmp_path)
    assert list(index.keys()) == sorted(index.keys())


def test_clearance_placement_and_removal_reflected_on_rerun(tmp_path: Path) -> None:
    # R6/I7 — the index mirrors operator file existence per run; I14 —
    # code never touches the clearance file itself.
    _build_three_day_ledgers(tmp_path)
    cid = _write_clearance(tmp_path, _URL_A)
    clearance_path = clearances_dir_for(ledger_root=tmp_path) / f"{cid}.manifest.json"
    authored_bytes = clearance_path.read_bytes()

    report = update_index(date(2026, 7, 16), ledger_root=tmp_path)
    assert report.cleared == 1
    assert report.invalid_clearances == 0
    assert _load_index(tmp_path)[cid]["rights_state"] == "cleared"
    assert clearance_path.read_bytes() == authored_bytes  # I14 read-only

    clearance_path.unlink()  # operator removal
    report = update_index(date(2026, 7, 16), ledger_root=tmp_path)
    assert report.cleared == 0
    assert _load_index(tmp_path)[cid]["rights_state"] == "metadata-only"


def test_blocked_marker_wins_over_coexisting_manifest(tmp_path: Path) -> None:
    # I7 precedence — blocked is the fail-safe state.
    _build_three_day_ledgers(tmp_path)
    cid = _write_clearance(tmp_path, _URL_A)
    (clearances_dir_for(ledger_root=tmp_path) / f"{cid}.blocked").touch()

    report = update_index(date(2026, 7, 16), ledger_root=tmp_path)
    assert report.blocked == 1
    assert report.cleared == 0
    assert _load_index(tmp_path)[cid]["rights_state"] == "blocked"


def test_url_identity_mismatch_is_not_cleared(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # I9 — a clearance authored for URL B under candidate A's filename
    # never clears A.
    _build_three_day_ledgers(tmp_path)
    cid = _write_clearance(tmp_path, _URL_A, source_url="https://img.example.com/other.jpg")

    with caplog.at_level(logging.WARNING, logger="investo.visuals.image_library"):
        report = update_index(date(2026, 7, 16), ledger_root=tmp_path)

    assert report.cleared == 0
    assert report.invalid_clearances == 1
    assert _load_index(tmp_path)[cid]["rights_state"] == "metadata-only"
    assert "does not hash to" in caplog.text


def test_unparseable_manifest_degrades_to_metadata_only(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # I8 — fail-closed runtime parse; the CI gate (Step 5) is the RED
    # enforcement.
    _build_three_day_ledgers(tmp_path)
    cid = candidate_id_for_url(_URL_A)
    clearances = clearances_dir_for(ledger_root=tmp_path)
    clearances.mkdir(parents=True, exist_ok=True)
    (clearances / f"{cid}.manifest.json").write_text("{broken", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="investo.visuals.image_library"):
        report = update_index(date(2026, 7, 16), ledger_root=tmp_path)

    assert report.cleared == 0
    assert report.invalid_clearances == 1
    assert _load_index(tmp_path)[cid]["rights_state"] == "metadata-only"
    assert "unparseable" in caplog.text


def test_non_explicit_license_kind_is_not_cleared(tmp_path: Path) -> None:
    # E3 — curated-licensed manifests belong to the u86 library, not the
    # per-candidate clearance contract.
    _build_three_day_ledgers(tmp_path)
    cid = _write_clearance(tmp_path, _URL_A, kind="curated-licensed")

    report = update_index(date(2026, 7, 16), ledger_root=tmp_path)
    assert report.cleared == 0
    assert report.invalid_clearances == 1
    assert _load_index(tmp_path)[cid]["rights_state"] == "metadata-only"


def test_index_atomic_write_leaves_no_tmp_sibling(tmp_path: Path) -> None:
    _build_three_day_ledgers(tmp_path)
    update_index(date(2026, 7, 16), ledger_root=tmp_path)
    assert list(tmp_path.rglob("*.tmp")) == []


def test_no_ledgers_and_no_index_writes_nothing(tmp_path: Path) -> None:
    report = update_index(date(2026, 7, 16), ledger_root=tmp_path)
    assert report.candidates_indexed == 0
    assert not index_path_for(ledger_root=tmp_path).exists()


def test_existing_index_refreshes_to_empty_when_ledgers_removed(tmp_path: Path) -> None:
    # I6 derived-only: the index never carries state the ledgers cannot
    # re-derive — removal is reflected, not fossilized.
    _build_three_day_ledgers(tmp_path)
    update_index(date(2026, 7, 16), ledger_root=tmp_path)
    for year_dir in tmp_path.glob("[0-9][0-9][0-9][0-9]"):
        for ledger in year_dir.glob("*.jsonl"):
            ledger.unlink()

    report = update_index(date(2026, 7, 16), ledger_root=tmp_path)
    assert report.candidates_indexed == 0
    assert index_path_for(ledger_root=tmp_path).read_text(encoding="utf-8") == "{}\n"
