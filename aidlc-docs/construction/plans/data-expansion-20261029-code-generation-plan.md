# u43 KRX 월물 / u66 Coin Metrics 순유입 도입

## Stage Decision
- Functional Design: Required — `../data-expansion-20261029/functional-design/design.md` 작성 완료.
- NFR Requirements: Required — `../data-expansion-20261029/nfr-requirements/requirements.md` 작성 완료.
- NFR Design: 위 문서의 비용·시간·라이선스·실패 격리 계약으로 충족.
- Infrastructure Design: Skipped — 기존 Python/httpx/source registry/브리핑 발행 경로 재사용, 새 서비스·키 없음.
- Source of requirements: 사용자 1~2순위 도입 승인, 전일 source research, FR-001/002, US-008, NFR-002/003/004, DEBT-067/072.
- 기존 도입 승인은 설계·구현·검증을 포함. 별도 단계 확인을 반복하지 않음. 구현 단계에서는 commit/push/배포를 수행하지 않았으며, 2026-10-30 후속 요청으로 해당 범위가 승인됨.

## 실행
- [x] 1. 범위와 FD/NFR 작성, 공식 규칙·휴일·Community 응답/사용 조건 확인.
- [x] 2. `sources/krx_option_expiry.py`, `sources/coinmetrics_exchange_flows.py`, `models/exchange_flows.py`; source registry와 SourceSpec, lookahead 등록, 2026 휴일 누락 수정.
- [x] 3. `_internal/crypto_indicators.py`, publisher block 교체/heading 인식, briefing prompt의 일별·잠정·출처 계약 적용.
- [x] 4. 소스/모델/publisher 합성 replay, 실패 경로, routing 회귀 및 ruff/mypy/무료 API 검사.
- [x] 5. 별도 agent 코드 리뷰와 수정, live smoke 및 최종 cross-check.
- [x] 6. 공유 작업공간에 충돌 없이 통합, state/audit/debt/세션 기록. 운영 관측 잔여와 코드 완료 구분.

- 리뷰 보완 경로: `models/event_document.py`, `_internal/market_reference.py`, `publisher/event_edition.py`, `publisher/public_document.py`, `_internal/numeric_verify.py`, `orchestrator/pipeline.py`. native v3 호환 표시와 수집 clock 회귀 포함. 실제 운영은 schema 2 / role_v1이며 기존 모드를 유지함.

최종 공유 작업공간 검증: 집중 144 passed, 변경 source 17개 mypy 및 변경 Python ruff/무료 API 검사 통과. 기존 HTML 실패 1건은 별도 기록.
