# Functional Design Plan: u180-public-insights-snapshot-and-publication

작성일: 2026-10-12 · u180 · 상태: 사용자 “유닛 하나씩 진행시켜” 지시로 설계 채택, 로컬 구현·검증 진행. 공개/운영 활성화는 pending.

## 작성 근거와 결정

[Answer]: 사용자가 세 화면 순서와 유닛 설계를 지시했다. 현재 값 우선·일정 7/30 일·무료/기존정적플랫폼·추가 LLM0 은 선택된 2026-10-11 기획과 이번 사용자 지시에서 계승한다. 하위 단위/clock/실패·보관/게시 방식은 설계자의 제안이며 산출물 승인을 자동 기록하지 않는다. 새 정보가 필요해지는 source qualification 은 blocked 로 모델링했고 임의 승인으로 채우지 않았다.

- [x] 현재 원격 코드·기존 owner·제품 선택/순서·중복 범위를 대조했다.
- [x] business-logic-model 의 입력/흐름/실패와 domain-entities 를 작성했다.
- [x] source/time/unit/identity/publication 규칙을 business-rules 에 고정했다.
- [x] foundation 은 consumer UI 가 없음을 명시했다. 실제 화면/hub 는 u181 이 소유한다.
- [x] 코드 계획·공통계약·FR/US/AC·의존성 참조를 대조했다.
- [x] 사용자 후속 구현 지시 “유닛 하나씩 진행시켜”를 기록하고 u180 설계를 채택했다.

초안 작성 이후 사용자 후속 진행 지시로 u180 Functional Design을 채택했다. 후속 화면 u181–u183과 source qualification/운영 수용은 각각 별도로 기록한다. 산출물은 해당 unit 의 functional-design 폴더에 있다.
