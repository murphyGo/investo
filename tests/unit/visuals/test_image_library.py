"""Tests for ``investo.visuals.image_library`` (u137 Step 1).

Pins FD Contract #1 / E1 / R2-R4 / I1-I4 for the candidate ledger:
identity normalization (I1), sanitize + caps (I2/R4), target-date
provenance (I3), byte-determinism + merge-rewrite idempotency with
existing-row-wins (I4/R3), imageless skip + same-run first-wins dedup
(R3), atomic-write convention, and R13 (AC-1.3) — including the
fail-closed URL screening documented in the module docstring.

All filesystem writes go to ``tmp_path`` — never the real ``archive/``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo.models import NormalizedItem
from investo.visuals.image_library import (
    ImageCandidateRecord,
    append_candidates,
    candidate_id_for_url,
    ledger_path_for,
    normalize_image_url,
)

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

    import logging

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
