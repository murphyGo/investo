# u162 교차 독립 리뷰

판정: **APPROVE — 검토 범위 내 미해결 P1/P2 없음**. 세 작성자가 모델/근거, 조합, 실제 최종화 테스트를 분리 구현했다. 부모가 reader/finalizer를 연결한 뒤 근거 작성자가 lifecycle/composition을, 조합 작성자가 근거/model을 읽기 전용으로 검토했다. 구현 1wave/검토 1wave이며 수정과 재검은 같은 검토 wave에 포함한다. 자신의 수정은 독립 검토로 계수하지 않았다.

구현 중 실제 최종화 테스트가 찾은 보완:

1. generated layout의 region index가 비어 있던 숫자 snapshot을 기존 §⑥ 소유자의 원문 구간으로 변경했다.
2. 서로 다른 기준선 가격의 `000.00` 접미사를 같은 용어로 오인해 등락률을 지우던 cosmetic pass에서 event 경로의 canonical 표를 보존했다.
3. 사건이 전부 제거된 뒤에도 전체 numeric baseline을 보관·복원하여 두 번째 최종화에서 6개 카드가 fallback2로 바뀌지 않게 했다.

실제 finalizer 독립 테스트 **24개/2.49s**가 통과했다. source·numeric·compliance gate는 mock하지 않았으며, 편집 시점 hook으로 삭제·변조를 재현했다.

교차 독립 리뷰에서 나온 두 P2는 모두 종결했다.

| 발견 | 수정 및 독립 재검 |
|---|---|
| detail_limited를 출처 링크 제거와 혼동해 유효 카드를 제외하고 finalization_removed로 오기록 | 실제 source locator 완전성을 별도 추적한다. 원래 반례는 카드 유지, 실제 링크 삭제는 source_locator_missing을 기록한다. 반복 Markdown SHA/companion도 동일하며 조합+실제 finalizer **50개/2.89s** 통과. |
| HTML 숨김/raw 컨테이너 내부 canonical 카드를 terminal 표시로 계수 | 열린 HTML 컨테이너 내부 카드를 read-only gate에서 거부한다. 원래 div hidden/script/pre 반례가 leaf와 실제 finalizer에서 차단되고 완료된 sibling HTML은 허용된다. 독립 회귀 **21개/1.55s** 통과. |

| 검토 범주 | 결과 |
|---|---|
| 정확성 | 명시적 kind union, source-addressed 현재 상태/다음 확인, caps 및 반복 최종화 검증 통과 |
| 보안·신뢰 | 원문 숫자·entity·compliance finding 보존, HTML literal/숨김 차단, 비밀·새 I/O 없음 |
| 설계·유지보수 | 기존 numeric resolver 및 finalizer 소유권 유지, immutable baseline/private companion 사용 |
| 회귀·테스트 | 최종 focused **222개/9.84s**, 전체 **6087개/460.18s**, 실제 finalizer와 sibling 음성 대조 포함 |
| 정책·운영 경계 | Ruff/format661/mypy290 및 정책4 통과; 기본 off와 운영 gate 유지 |

전체 테스트 시작 시 고정한 변경 source/test 10개 SHA-256이 완료 후에도 동일함을 확인했다. 실제 운영 의미 평가·scheduled shadow·게시/알림/Pages 수용 검증은 이 코드 리뷰의 완료 주장에 포함하지 않는다.
