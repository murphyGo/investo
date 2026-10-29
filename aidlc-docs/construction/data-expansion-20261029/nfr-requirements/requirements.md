# 비기능 계약과 공개 자격

- 추적: FR-001 수집, FR-002 시황 근거, US-008 adapter, 기존 u43/u66, DEBT-067/072, NFR-002 무료, NFR-003 독립적 실패, NFR-004 고지, R8 strict metadata, R10 fixture, R13 secret hygiene.
- 비용: KRX 로컬 계산 0원/요청 없음. Coin Metrics Community 무키 호출만, 유료 fallback 없음. 공통 retry/backoff/body cap와 최대 6행 schema cap 적용. 10회/6초 upstream 제한 내 일일 배치와 최대 2회 재시도.
- 공개: 현 1인 비상업 Investo 범위에서만 CC BY-NC 4.0 데이터를 표시한다. deterministic output에 Coin Metrics 링크, 라이선스 링크, Investo 계산·잠정/수정·추적 주소 범위를 명시한다. 공개 사이트 및 해당 브리핑의 Git 보존에는 같은 고지를 유지한다. Telegram은 상세보기 링크로 출처·라이선스가 있는 페이지에 연결한다. native 알림에는 시장 기준 패널 수치를 복사하지 않는다. 상업 이용 전에는 `INVESTO_SOURCE_DISABLE=coinmetrics-exchange-flows`로 비활성화하고 별도 허가를 확인한다. API 수집 가능성을 상업 표시권으로 해석하지 않음.
- 테스트 fixture는 직접 만든 합성 값이다. 실측 원문은 임시 경로에만 보관하며 공개 테스트에 원문 값/비밀을 복사하지 않는다. 관측 provenance는 해시·행 수·상태·날짜만 기록한다.
- 시간/정확도: Decimal context를 충분히 크게 설정하여 subtraction에 반올림 없음. 소수 문자열 길이/자릿수 제한. 미래 상태시간/미완료 UTC 일자 제외. reviewed도 향후 수정 가능하므로 확정/실시간이라고 쓰지 않는다.
- 회귀: registry/tiers/window/routing, invalid/empty/timeout/429, 날짜·연속 휴장·미지원 연도, publisher 최종 attribution 교체 및 미수집/부분 수집. 기존 인사이트 snapshot schema/운영 권한 목록은 변경하지 않음.
- 운영 인수: 코드·로컬 replay/live probe와 예약 GHA 관측은 별도. 이 작업에서 배포/외부 채널 송신/전체 debt 완료를 주장하지 않는다. 연도 갱신과 첫 예약 실행 관측은 잔여 운영 항목.
