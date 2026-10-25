# Functional Design Plan: u181-macro-environment-dashboard

설계 2026-10-12 · 구현 검증 2026-10-25 · 사용자 후속 진행 지시로 설계 채택. 로컬 7/8 완료, 운영 Step8 pending.

## 작성 근거와 결정

[Answer]: 사용자가 세 화면 순서와 유닛 설계를 지시했다. 현재 값 우선·일정 7/30 일·무료/기존정적플랫폼·추가 LLM0 은 선택된 2026-10-11 기획과 이번 사용자 지시에서 계승한다. 하위 단위/clock/실패·보관/게시 방식은 설계자의 제안이며 산출물 승인을 자동 기록하지 않는다. 새 정보가 필요해지는 source qualification 은 blocked 로 모델링했고 임의 승인으로 채우지 않았다.

- [x] 현재 원격 코드·기존 owner·제품 선택/순서·중복 범위를 대조했다.
- [x] business-logic-model 의 입력/흐름/실패와 domain-entities 를 작성했다.
- [x] source/time/unit/identity/publication 규칙을 business-rules 에 고정했다.
- [x] UI 가 있는 유닛은 frontend-components 를 작성하고 공통 noJS/테마/viewport 수용을 명시했다.
- [x] 코드 계획·공통계약·FR/US/AC·의존성 참조를 대조했다.
- [x] 사용자 “진행시켜” 후속 지시로 u181 설계를 채택하고 로컬 구현·검증을 기록했다.

후속 사용자 지시로 u181 Functional Design을 채택하고 Code Generation Steps1–7을 검증했다. 운영 수용은 별도다. 산출물은 해당 unit 의 functional-design 폴더에 있다.
