# u182 independent code review — final

작성일: 2026-10-25. 별도 reviewer. 현재 확인한 미해결 **Critical 0 / High 0 / Medium 0**.

초기 검토의 범위·protocols·검증 출처·한계는 [review-u182-initial.md](review-u182-initial.md)에 기록되어 있다. 이번 후속 검토는 M182-01의 Fed source-local occurrence identity 수정과 해당 recording 회귀에 한정한다. 전체 구현을 새로 전수 검토하거나 전체 suite를 반복 실행한 것은 아니다.

## M182-01 해결 확인

`fomc_calendar._insight_event()`가 title-only hash를 제거하고 정규화한 title/time/location/description의 canonical SHA256으로 `fed:own:` identity를 만든다. 기존 occurrence key의 kind/현지 날짜/기간과 결합하여 같은 발표자의 당일 별도 행사를 구별한다. 원천 시각과 설명은 구별용 hash 입력이며 공개 exact timestamp나 복사한 본문으로 출력되지 않는다. 공개 clock은 계속 date precision이며 exact_at=None이다.

추가 회귀는 기존 실제 recording의 2026-02-09 Stephen I. Miran 두 Discussion 행사를 adapter offline replay로 수집하고 서로 다른 event_id 및 projection 두 건을 검증한다. reviewer가 해당 테스트를 직접 실행했다.

```text
.venv/bin/python -m pytest tests/unit/sources/test_upcoming_insights_envelopes_u182.py::test_recorded_distinct_same_speaker_fed_events_keep_separate_occurrences -q
1 passed in 1.08s
```

초기 리뷰의 별도 직접 재현도 같은 recording/날짜/qualification/실제 projection으로 재실행했다.

```text
source distinct occurrences 2 unique typed identities 2 projected events 2 conflicts 0 invalid 0
public precision/exact_at [('date', None), ('date', None)]
```

따라서 두 실제 행사 손실 및 conflict 없이 하나로 합쳐지는 초기 문제를 해결한 것으로 판정한다. 이 좁은 후속 검토에서 새로운 Critical/High/Medium finding은 없다.

## 검증과 운영 경계

초기 u182 관련 reviewer 직접 실행은 45 passed in 11.72s였으며 이번 직접 실행은 위 단일 회귀와 별도 recording 재현이다. lead가 전달한 source20/static Ruff·format772·mypy325/Chromium16조합 결과는 lead의 별도 실행 증거이며 reviewer 직접 실행으로 계산하지 않는다.

권리 qualification의 실제 법적 수용, 새 production source 요청, 실제 viewport 독립 수용, Pages/private pin/activation 및 scheduled 운영 수용을 이 보고서로 승인하거나 완료했다고 주장하지 않는다. 구현·테스트 변경, commit/push/배포 없이 보고서만 작성했다.
