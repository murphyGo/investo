# u158 독립 코드 리뷰

2026-09-27, baseline d5aa8f28. 두 wave 안에서 구현과 교차 검토를 수행했다. producer 담당자는 parent integration을 검토했고, 독립 QA는 producer/finalizer를 검토했다. 독립 리뷰의 8건과 통합 중 발견한 3건을 수정했다. 미해결 P1/P2는 없으며 최종 전체 5,521개 회귀가 통과했다(402.28초). 결과: PASS.

| 발견 | 교정 및 회귀 |
|---|---|
| P2 가격 부족을 뉴스 수집 부족으로 표시 | event collection 판정을 분리했다. 성공한 0건, 수집 증거 없음, 뉴스 source 실패를 구분한다. |
| P2 짧지만 유효한 v2 JSON 거부 | 기존 200자 Markdown 하한은 v1에만 유지한다. v2는 strict schema/내용 검증을 사용한다. |
| P2 검증된 reaction/date 숫자를 미확인으로 경고 | 실제 전달된 narrative refs와 typed timestamp만 추가 숫자 근거로 사용한다. |
| P2 prompt와 source_refs 필수 포함 규칙 불일치 | actor/action/object/fact/meaning/reaction refs 합집합 및 필드별 숫자 규칙을 명시했다. |
| P2 headline/meaning/reaction 실제·예상 수치 교환 | 각 public slot의 typed fact 역할을 검사한다. 양성·역전 수치 각 3개를 검증했다. |
| P2 unvalidated model_copy 정규화 결과 미사용 | 타입을 보존해 재검증한 뒤 canonical JSON 동등성을 확인한다. 비정규 timezone/dict 복사는 원문·warning 없이 closed code로 거부한다. |
| P2 변조 source의 ellipsis 면제 및 출처 라벨 변조 | canonical label/URL을 대조한다. 동일 host의 실제 URL 접두가 끝에서 잘린 경우만 limited이며 다른 host/label 변조는 삭제 전에 hard block이다. |
| P2 HTML/Markdown escape가 terminal DTO에 노출 | escaped literal과 숫자 강조를 구분하고 HTML entity를 복원한다. AT&T/Acme_Labs의 모든 DTO 필드와 재처리 bytes를 확인했다. 첫 문장은 공통 complete-sentence helper로 판정한다. |
| P2 의미/반응/제목 변조가 구조적 삭제로 숨을 가능성 | 존재하는 필드의 변경은 canonical과 대조하여 hard finding을 보존한다. 단순 필드 누락과 구분하며 sibling 생존을 확인했다. |
| P2 다중 사건의 날짜 정밀도 설명이 용어 dedup으로 삭제 | event mode에서 순수 glossary dedup만 structured event child를 보존한다. 모든 hard/repair pass는 전체 원문을 그대로 검사한다. 숫자 강조는 terminal plain-text 비교에서 허용한다. |
| P2 TL;DR 뒤에 있는 callout/hero까지 내용 교체 범위에 포함 | 선행 요약 문단만 교체하고 뒤의 별도 블록은 그대로 보존한다. 현재 배치와 u154에서 제안한 summary-before-hero 배치 2개 합성 fixture의 순서·bytes·재실행 동일성을 확인했다. |

부모 수정 4건과 producer/finalizer 수정 4건은 원래 재현으로 독립 재확인했다. 초기 탐색에서는 preview의 public entry/boot alert 진입, 실제 prompt lineage, typed payload 전달을 확인했고 구현에 반영했다. 최종 publisher unit/integration은 42개 통과(1.94초)했으며 기존 7개 섹션과 면책의 실제 HTML 표현도 확인했다.

검토 범주: correctness, typed boundary, privacy, compatibility, finalizer ownership, failure isolation, resource bounds. 자유 서술의 모든 의미를 자동 증명한다는 주장은 하지 않는다. 실제 provider 서비스나 운영 게시를 실행하지 않았다.

최초 전체 회귀에서 5,517개 통과와 기존 architecture/봉인 호출 검사 2개 실패를 확인했다. 승인된 assembly phase 안의 summary mutation만 allowlist에 추가했고, 사건 receipt가 없는 경우 기존 봉인 함수 인자를 그대로 유지했다. seal call site는 하나다. 관련 75개 회귀가 통과했으며 최종 전체 gate를 다시 실행했다.

이후 전체 5,519개가 통과했다(404.22초). 마지막 preamble 호환성 교정 뒤 finalizer/상단 배치/preview 112개가 통과했으며, 추가된 2개 fixture를 포함한 최종 전체 5,521개가 통과했다(402.28초).
