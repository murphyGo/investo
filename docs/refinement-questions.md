# Refinement Questions: Investo

**Date**: 2026-04-25

## Architecture & Tech Stack

Q1: 데이터 소스 선호 (무료 위주 vs 유료 품질)?
[Answer]: 무료 위주로 시작.

Q2: LLM 선택은 Claude API (anthropic SDK)? 다른 모델?
[Answer]: Claude Code의 setup token으로 Claude Code CLI를 GitHub Actions에서 실행. Anthropic API key 직접 호출은 별도 요금이 있어 불가.

## Scope & Features

Q3: 사용자 범위 (본인 전용 / 지인 공유 / 공개 서비스)?
[Answer]: 본인 전용, 하지만 남한테 보여줄 수도 있음 (public 열람 가능).

Q4: 시황 언어 (한국어 / 영문 혼용)?
[Answer]: 한국어 (영문 종목명/티커는 원문 유지).

Q5: 이력 보관 기간?
[Answer]: 영구 보관, 문제가 될 정도로 많아지면 그때 삭제 고려.

## Non-Functional Requirements

Q6: 보호해야 할 민감 정보가 있나? (개인 포트폴리오 등)
[Answer]: 현재는 없음.

## Extension Opt-in

Q-Ext-A: Security Baseline extension 적용?
[Answer]: SKIP (본인용 작은 도구, 민감 데이터 없음, public repo).

Q-Ext-B: Property-Based Testing extension 적용?
[Answer]: Partial — 순수 함수 및 직렬화 round-trip에만 적용.

## Ambiguity Resolutions

- "주요 소스" → Q1 답변과 NFR-002(비용 0원)에서 무료 소스만으로 확정. 정확한 조합은 Open Questions로 보관, 구현 PoC에서 결정.
- "시황을 만들어준다" → Q2 답변으로 LLM 호출 방식이 Claude Code CLI로 확정. 일반적인 anthropic SDK 사용 패턴 대비 구현이 다르므로 NFR-002·FR-002 acceptance criteria에 명시.
- "투자 조언" 표현 위험 → 사용자가 별도 언급은 없었으나 컴플라이언스 리스크가 명확하여 NFR-004로 면책조항 자동 삽입 의무화.
