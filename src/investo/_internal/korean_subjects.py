"""Separate grammatical subjects from conservative source entity candidates."""

from __future__ import annotations

import re
from collections.abc import Iterator

_SUBJECT = re.compile(r"([가-힣A-Za-z][가-힣A-Za-z0-9_.-]{1,})[이가은는](?=\s)")
# These are reader roles, data-field concepts and action categories, not
# organization aliases. Exact words only: `정보` never licenses `정보테크`.
_CONCEPTS = frozenset(
    {
        "의미",
        "반응",
        "시장",
        "변화",
        "조건",
        "가능성",
        "결과",
        "전제",
        "영향",
        "배경",
        "사건",
        "확인",
        "이",
        "그",
        "이번",
        "수치",
        "일정",
        "발표",
        "내용",
        "작동",
        "경로",
        "관측값",
        "단위",
        "데이터",
        "정보",
        "자료",
        "원문",
        "근거",
        "설명",
        "주체",
        "대상",
        "행동",
        "사실",
        "문장",
        "기간",
        "시점",
        "보고서",
        "계약",
        "합의",
        "협약",
        "체결",
        "제품",
        "서비스",
        "출시",
        "승인",
        "결정",
        "정책",
        "발언",
        "의결",
        "취소",
        "종료",
        "완료",
        "재개",
        "원인",
        "목적",
        "방식",
        "범위",
        "상태",
        "계획",
        "전망",
        "예상",
        "가정",
        "한계",
        "부분",
    }
)
_MODIFIER = re.compile(r"[가-힣]+(?:하는|되는|있는|없는|같은|않는|따른|위한)$")


def korean_entity_subjects(text: str) -> Iterator[str]:
    """Yield unresolved noun subjects, without treating verb modifiers as names."""
    for match in _SUBJECT.finditer(text):
        token = match.group().strip()
        label = match.group(1)
        if _MODIFIER.fullmatch(token) or label in _CONCEPTS:
            continue
        yield label
