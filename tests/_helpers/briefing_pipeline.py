"""Shared helper payloads for briefing pipeline tests."""

from __future__ import annotations

import json


def valid_classification_stdout(item_count: int) -> str:
    """Stage 1 stdout that assigns every item to section 4."""
    assignments = {str(i): 4 for i in range(1, item_count + 1)}
    return json.dumps({"assignments": assignments, "unassigned": []})


def valid_stage2_markdown() -> str:
    """Stage 2 stdout that parses cleanly and clears the sanity floor."""
    return (
        "## ① 요약\n오늘 시장의 한 줄 요약 본문입니다 추가 패딩 텍스트도 함께\n\n"
        "## ② 전일 핵심 이슈\n전일의 핵심 이슈를 상세히 설명하는 본문 텍스트입니다\n\n"
        "## ③ 섹터/수급 동향\n섹터별 수급 동향을 정리한 본문 텍스트입니다\n\n"
        "## ④ 지표·이벤트\n주요 거시 지표와 일정 이벤트를 정리한 본문입니다\n\n"
        "## ⑤ 주요 종목\n관심 종목 흐름을 정리한 본문 텍스트입니다\n\n"
        "## ⑥ 오늘의 관전 포인트\n오늘 살펴볼 포인트를 정리한 본문 텍스트입니다\n"
    )
