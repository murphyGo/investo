# Functional Design Plan: u182-upcoming-events-dashboard

작성일: 2026-10-12 · u182 · 상태: 2026-10-25 사용자 “진행시켜” 지시로 설계 채택. 운영 활성화는 별도다.

## 작성 근거와 결정

[Answer]: 사용자가 세 화면 순서와 유닛 설계를 지시했다. 현재 값 우선·일정 7/30 일·무료/기존정적플랫폼·추가 LLM0 은 선택된 2026-10-11 기획과 이번 사용자 지시에서 계승한다. 하위 clock/실패·보관/게시 방식은 후속 진행 지시로 이번 로컬 구현에 채택했다. 새 정보가 필요해지는 source qualification 은 blocked 로 모델링했고 임의 승인으로 채우지 않았다.

- [x] 현재 원격 코드·기존 owner·제품 선택/순서·중복 범위를 대조했다.
- [x] business-logic-model 의 입력/흐름/실패와 domain-entities 를 작성했다.
- [x] source/time/unit/identity/publication 규칙을 business-rules 에 고정했다.
- [x] UI 가 있는 유닛은 frontend-components 를 작성하고 공통 noJS/테마/viewport 수용을 명시했다.
- [x] 코드 계획·공통계약·FR/US/AC·의존성 참조를 대조했다.
- [x] 사용자 후속 “진행시켜” 지시로 기존 설계 채택과 로컬 구현 범위를 기록했다.

설계 산출물은 2026-10-25 후속 구현 지시로 채택했다. 실제 배포/운영 수용은 별도다. 산출물은 해당 unit 의 functional-design 폴더에 있다.
