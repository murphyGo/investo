"""Real paths, sealed current snippets, exact future seams and atomic failures."""

import os
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from investo.publisher.site_index import segment_archives as archive
from investo.publisher.site_index.archive_sections import _latest_segment_entry_before
from tests._helpers.reader_fixture_u178 import build_reader_fixture


def put(root, name, folder="2026/10"):
    path = root / folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("historical body must never be read")
    return path


def test_months_keep_every_safe_actual_path_without_reading_history(tmp_path, monkeypatch):
    root = tmp_path / "us-equity"
    latest = put(root, "2026-10-07.md")
    old = put(root, "2026-09-01.md", "2026/09")
    put(root, "bad <name>.md")
    mismatch = put(root, "2026-08-01.md")
    outside = put(tmp_path / "outside", "2026-10-08.md")
    (root / "2026/10/2026-10-08.md").symlink_to(outside)
    (root / "2026/10/2026-10-09.md").mkdir()
    (root / "2026/10/dangling.md").symlink_to(root / "absent.md")
    (root / "2026/10/not-directory.md").symlink_to(latest / "child")
    loop = root / "2026/10/loop.md"
    loop.symlink_to(loop)

    def no_history(path, *args, **kwargs):
        raise AssertionError(f"historical read: {path}")

    monkeypatch.setattr(Path, "read_text", no_history)
    written = []
    monkeypatch.setattr(archive, "_write_text_atomic", lambda path, text: written.append(text))
    index = root / "index.md"
    assert archive.update_segment_archive_index("us-equity", segment_index_path=index) == index
    text = written[0]
    assert text.index("2026년 10월") < text.index("2026년 09월")
    assert text.count('class="investo-archive-entry"') == 2
    assert "2026/10/2026-08-01.md" in text
    assert "bad%20%3Cname%3E.md" in text and "bad &lt;name&gt;.md" in text
    assert "2026-10-08" not in text and "2026-10-09" not in text
    assert "경로 확인이 필요한 문서" in text and "hidden" in text
    assert "investo-archive-snippet" not in text
    assert _latest_segment_entry_before(root, before=date(2026, 10, 8)) == latest
    assert old in archive._segment_entries(root) and mismatch in archive._segment_entries(root)


def test_empty_archive_and_filter_zero_are_different(tmp_path):
    text = archive._render_segment_index("crypto", "크립토", [])
    assert "현재 표시할 시황이 없습니다" in text and "investo-archive-controls" not in text


def test_only_real_current_seal_can_supply_legacy_snippet_and_future_view_is_exact(tmp_path):
    bundle = build_reader_fixture(tmp_path / "staging")
    doc = next(d for d in bundle.documents if d.segment == "us-equity")
    entry = put(tmp_path / "us-equity", doc.target_date.isoformat() + ".md")
    historical = put(tmp_path / "us-equity", "2026-10-06.md")
    original = doc.briefing.rendered_markdown
    text = archive._render_segment_index(
        "us-equity", "미국 증시", [entry, historical], finalized_documents={entry: doc}
    )
    assert text.count('class="investo-archive-snippet"') == 1
    assert "확인된 수집 근거의 조건을 정리했습니다." in text
    assert doc.briefing.rendered_markdown == original
    headline = "마침표 없는 확정 헤드라인 <script> & 제한"
    digest = "가" * 140
    exact = archive._render_segment_index(
        "us-equity",
        "미국 증시",
        [entry, historical],
        finalized_documents={entry: doc},
        terminal_snippets={historical: digest},
        terminal_limitations={entry: headline},
    )
    assert exact.count('class="investo-archive-snippet"') == 1
    assert digest in exact and "&lt;script&gt; &amp; 제한" in exact
    assert "확인된 수집 근거의 조건을 정리했습니다." not in exact
    assert 'markdown="0"' in exact


@pytest.mark.parametrize(
    "value", ["끝나지 않은 헤드라인", "첫 문장. " + "제한" * 70 + ".", "완결. 미완결 꼬리"]
)
def test_legacy_snippet_never_silently_drops_a_limitation(value):
    doc = SimpleNamespace(briefing=SimpleNamespace(rendered_markdown="> **오늘의 결론**: " + value))
    assert archive._legacy_snippet(doc) is None


def test_atomic_failure_preserves_previous_index(tmp_path, monkeypatch):
    root = tmp_path / "crypto"
    put(root, "2026-10-07.md")
    index = root / "index.md"
    index.write_text("previous index")
    original = os.replace

    def fail(path, target):
        if Path(target) == index:
            raise OSError("synthetic replace failure")
        return original(path, target)

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="replace failure"):
        archive.update_segment_archive_index("crypto", segment_index_path=index)
    assert index.read_text() == "previous index"


@pytest.mark.parametrize("denied", ["", "2026/10"])
def test_directory_read_error_propagates_and_retains_index(tmp_path, monkeypatch, denied):
    root = tmp_path / "crypto"
    put(root, "2026-10-07.md")
    index = root / "index.md"
    index.write_text("previous index")
    original = os.listdir

    def unreadable(path):
        if Path(path) == root / denied:
            raise PermissionError("synthetic unreadable archive")
        return original(path)

    monkeypatch.setattr(os, "listdir", unreadable)
    with pytest.raises(PermissionError, match="unreadable"):
        archive.update_segment_archive_index("crypto", segment_index_path=index)
    assert index.read_text() == "previous index"


def test_directory_mismatch_stays_reachable_but_cannot_supply_latest_fallback(tmp_path):
    root = tmp_path / "us-equity"
    actual = put(root, "2026-10-07.md")
    mismatch = put(root, "2026-12-01.md")
    assert mismatch in archive._segment_entries(root)
    assert _latest_segment_entry_before(root, before=date(2027, 1, 1)) == actual


def test_legacy_summary_uses_existing_plain_owner_and_never_activates_markdown():
    from investo._internal.public_summary_extract import clean_public_summary_text

    raw = (
        "**수치**와 [기사](javascript:alert%281%29), "
        "![이미지](https://example.invalid/x)를 확인합니다."
    )
    doc = SimpleNamespace(briefing=SimpleNamespace(rendered_markdown="> **오늘의 결론**: " + raw))
    assert archive._legacy_snippet(doc) == clean_public_summary_text(raw)
    assert doc.briefing.rendered_markdown.endswith(raw)
