"""Unit tests for u57 Step 5 — shared macro ``## ⓪`` injection."""

from __future__ import annotations

from investo.publisher.shared_macro import (
    SHARED_MACRO_HEADER,
    inject_shared_macro_block,
)

BLOCK = "- **국제 유가** — WTI 80$\n- **미 국채 수익률** — UST 4.42%"


class TestNoBlock:
    def test_none_block_returns_unchanged(self) -> None:
        text = "## 한눈에 보기\n\n- foo\n\n## ① 요약\n\nbody"
        assert inject_shared_macro_block(text, None) == text

    def test_empty_block_returns_unchanged(self) -> None:
        text = "## ① 요약"
        assert inject_shared_macro_block(text, "") == text


class TestInjectionSite:
    def test_after_tldr(self) -> None:
        text = "## 한눈에 보기\n\n- foo\n- bar\n- baz\n\n## ① 요약\n\nbody\n"
        out = inject_shared_macro_block(text, BLOCK)
        idx_tldr = out.find("## 한눈에 보기")
        idx_macro = out.find(SHARED_MACRO_HEADER)
        idx_one = out.find("## ① 요약")
        assert idx_tldr < idx_macro < idx_one

    def test_before_section_one_when_no_tldr(self) -> None:
        text = "## ① 요약\n\nbody\n"
        out = inject_shared_macro_block(text, BLOCK)
        idx_macro = out.find(SHARED_MACRO_HEADER)
        idx_one = out.find("## ① 요약")
        assert idx_macro < idx_one

    def test_appended_when_no_anchors(self) -> None:
        text = "just some text without sections"
        out = inject_shared_macro_block(text, BLOCK)
        assert SHARED_MACRO_HEADER in out
        # Appended at end → section header position is after original.
        assert out.find(SHARED_MACRO_HEADER) > len(text) - 1


class TestIdempotence:
    def test_block_already_present(self) -> None:
        text = f"## 한눈에 보기\n\n- x\n\n{SHARED_MACRO_HEADER}\n\n- already there\n\n## ① 요약\n"
        out = inject_shared_macro_block(text, BLOCK)
        assert out == text
        # ``## ⓪`` should appear exactly once.
        assert out.count(SHARED_MACRO_HEADER) == 1

    def test_double_call_idempotent(self) -> None:
        text = "## ① 요약\n\nbody"
        once = inject_shared_macro_block(text, BLOCK)
        twice = inject_shared_macro_block(once, BLOCK)
        assert once == twice
        assert twice.count(SHARED_MACRO_HEADER) == 1


class TestBodyShape:
    def test_block_body_included(self) -> None:
        text = "## ① 요약"
        out = inject_shared_macro_block(text, BLOCK)
        assert "국제 유가" in out
        assert "미 국채 수익률" in out
