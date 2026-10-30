"""Separate grammatical subjects from conservative source entity candidates."""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence

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
        "확대",
        "인과관계",
        "상태",
        "계획",
        "전망",
        "예상",
        "가정",
        "한계",
        "부분",
        "성명",
        "조치",
        "목표",
        "금리",
        "기준금리",
        "정책금리",
        "목표범위",
        "인상",
        "인하",
        "동결",
        "인플레이션",
        "물가",
        "고용",
        "실업률",
        "경제활동",
        "생산성",
        "자본투자",
        "투자",
        "국내지출",
        "지출",
        "지급준비금",
        "불확실성",
        "증가",
        "증가세",
        "축적",
        "표결",
        "발행일",
        "지표",
        "실제치",
        "비교값",
        "이전값",
        "수준",
        "활동",
        "경제",
        "경기",
        "성장",
        "성장률",
        "물가상승률",
        "물가안정",
        "노동력",
        "상황",
        "여건",
        "기조",
        "추세",
        "흐름",
        "의지",
        "입장",
        "방침",
        "도움",
        "지원",
        "뒷받침",
        "보탬",
        "기여",
        "촉진",
        "노력",
        "역할",
        "수단",
        "효과",
        "효력",
        "추진",
        "정상화",
        "긴축",
        "완화",
        "규모",
        "긴장",
        "성장세",
        "준비금",
        "일자리",
        "노동",
        "임금",
        "소비",
        "수요",
        "공급",
        "물가상승",
        "인플레",
        "가격",
        "환율",
        "수익률",
        "채권금리",
        "주식",
        "채권",
        "지수",
        "거래량",
        "변동성",
        "자산",
        "부채",
        "매출",
        "이익",
        "영업이익",
        "순이익",
        "실적",
        "배당",
        "현금흐름",
        "유동성",
        "접근",
        "복귀",
        "회복",
        "확보",
        "유지",
        "안정",
    }
)
_MODIFIER = re.compile(
    r"(?:되돌리는|만드는|"
    r"[가-힣]+(?:하는|되는|있는|없는|같은|않는|따른|위한|하겠다는|되겠다는|한다는|했다는|됐다는))$"
)


def korean_entity_subjects(text: str) -> Iterator[str]:
    """Yield unresolved noun subjects, without treating verb modifiers as names."""
    for match in _SUBJECT.finditer(text):
        token = match.group().strip()
        label = match.group(1)
        concept = label in _CONCEPTS or any(
            label.endswith(suffix) and label[: -len(suffix)] in _CONCEPTS
            for suffix in ("에", "에서", "에게", "에게서", "으로", "로")
        )
        if _MODIFIER.fullmatch(token) or concept:
            continue
        yield label


def is_source_role_subject(
    label: str, source_words: set[str], *, proof_windows: Sequence[str] = ()
) -> bool:
    """A generic role translation needs that role in the very same claim proof.

    This does not license named bodies such as 금융위원회 or invented names
    ending in 위원회, and never creates a canonical entity or alias.
    """
    if label == "위원회":
        return "committee" in source_words
    if label == "은행지주회사":
        return any(re.search(r"\bbank\s+holding\s+company\b", text) for text in proof_windows)
    if label == "달러":
        return bool(source_words & {"usd", "dollar", "dollars"}) or any(
            re.search(
                r"\$\s*[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![A-Za-z0-9_.,])",
                text,
            )
            for text in proof_windows
        )
    return False
