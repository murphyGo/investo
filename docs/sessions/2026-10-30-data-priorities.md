# Session: 2026-10-30 — 데이터 확장 우선순위 적용

## 요청과 범위

사용자 “우선수위별로 적용하자”. 앞서 검토한 Coin Metrics 활동, EF 공지, KRX 위클리를 순서대로 판정/구현했다. EF·Deribit·Bybit의 미해결 이용·운영 조건은 보류한다. `dev-investo`와 독립 `code-review` 절차를 적용한다.

## 구현

- `models/network_activity.py`, `sources/coinmetrics_network_activity.py`, `_internal/network_activity.py`: BTC/ETH 2종 활동, 완료 UTC8일 최대16행, 64KiB, 연속7일평균, 부분실패와수정가능성.
- `_internal/crypto_indicators.py`, `_internal/numeric_verify.py`, `_internal/market_reference.py`, `models/event_document.py`, `publisher/event_edition.py`, `briefing/prompts.py`: source-backed 표와정확한수치검증, native/legacy 출처고지.
- `models/option_expiry.py`, `sources/krx_option_expiry.py`: 월/목위클리 구분, 공휴일양방향, 2026년범위, 수능일시간미검증 제외, 월물우선표시.
- `sources/__init__.py`, `_internal/source_specs.py`: 신규 source 등록/routing. 관련계약·회귀·통합테스트추가.

## 검증과 분리

[검증 기록](../../aidlc-docs/construction/data-priorities-20261030/validation.md), [자격 판정](../../aidlc-docs/construction/data-priorities-20261030/qualification.md), [cross-check](../cross-checks/2026-10-30-data-priorities.md). root가 여러 세션의 dirty 작업을 포함해 b121ca01 기준 별도 사본에서 개발·검증했다. 통합은 대상 파일별 baseline hash 확인 후 수행한다. 다른세션변경·root HEAD·index·기존 runtime pin은 변경하지 않는다.

## 독립 리뷰 / 통합

독립 reviewer의 최종 판정 및 공유 root 검증을 이 절에 기록한다.

### Final review and integration result

Independent reviewer `/root/data_expansion_review`: **Pass**, no blocking findings; 43 tests independently passed. The typed option panel is absent from persisted public editions and the LLM content schema, so current archive/prompt paths are unaffected. A future feature that reloads historical internal draft JSON would require an explicit migration. [Review](../../aidlc-docs/construction/data-priorities-20261030/review.md).

All 27 integration targets matched their root baseline and clone base. After integration, root passed **163 tests (1.90s)**, Ruff check/format (858 files) and mypy (363 files). State/audit/debt appendices preserve other sessions' records. The new changes are not committed or deployed.
