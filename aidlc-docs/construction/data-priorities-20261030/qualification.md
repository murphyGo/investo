# 데이터 확장 적용 판정 — 2026-10-30

사용자의 우선순위별 적용 지시에 따라 구현 가능한 범위를 진행했다. [직전 검토](../data-expansion-followup-20261030/review.md)의 조건부/보류 판정을 자동 승인으로 바꾸지 않는다.

| 순서 | 후보 | 이번 판정 | 근거 / 다시 열 조건 |
| --- | --- | --- | --- |
| 1 | Coin Metrics 활동 | BTC/ETH 활성 주소·거래 건수 구현 | 기존 Community CC BY-NC 4.0 비상업 범위, 별도 출처·계산 표시. 정확한 7일 평균, 결측 격리, 64KiB/16행 상한. 수수료 지표는 추가하지 않음 |
| 2 | EF 공식 공지 | 공개 source 등록 보류 | 공식 feed의 권리 표시와 재사용·보존 계약 미확정. 본문/발췌/메타데이터 각각 허용 범위를 확인한 뒤 재검토 |
| 3 | KRX 위클리 | 2026년 월/목 위클리 구현 | 월요일 휴장 후순연, 목요일 휴장 앞당김, 둘째 목요일 월물로 구분. 통상 정규장 최종거래 시각, 현재 상장 계약/최종결제일이 아님 |
| 후속 | Deribit | 보류 유지 | 시장/파생 데이터 공개 재전송 서면허가 필요 |
| 후속 | Bybit 청산 | 보류 유지 | 지속 수집·단절 복구·보존·공개 권한 필요. 짧은 cron 표본을 24시간 전체로 표시하지 않음 |

## KRX 자격 경계

- [KRX KOSPI 200 상품명세](https://global.krx.co.kr/contents/GLB/02/0201/0201040202/GLB0201040202.jsp): 월/목 위클리의 휴일 이동 방향, 둘째 목요일 제외, 최종거래일 정규장 15:20을 대조했다. 위클리는 향후 규칙 기반 일정이지 현재 상장 여부를 확인한 목록이 아니다.
- [교육부의 2027학년도 수능 시행일](https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=294&boardSeq=100526&lev=0&m=020402)은 **2026-11-19**다. 해당일 KRX 특별 거래시간 원문은 이번 검증에서 확보하지 못했다. 과거 수능일 시각을 재사용하거나 통상 15:20을 단정하지 않고 그 날짜의 위클리는 생성/수용에서 제외한다. 화면에도 제외 사실을 표시한다. KRX 당해 공지 검증 후 시간 예외와 테스트를 추가한다.
- [우주항공청 2027년 월력요항 발표](https://www.kasa.go.kr/prog/plcyBrf/brief/kor/sub01_01_04/view.do?plcyBrfNo=431)는 2026-06-29 공표됐다. 따라서 “2027년 공휴일 발표 자체가 없다”는 주장은 하지 않는다.
- 다만 고시 PDF·보도자료 HWPX의 다운로드 응답은 이번 실행에서 200 HTML 오류 페이지였고, [KASI 달력자료](https://astro.kasi.re.kr/kor/life/post/calendarData?year=2027)는 자체적으로 공식 발표 자료가 아니라고 표시한다. 거래소의 연말 휴장 및 특례까지 포함한 연간 자격은 완료하지 않았다. **2027년 일정 자동 생성은 계속 차단**한다. 공휴일 공표와 거래소 달력 자격을 구분한다.
- 2026-12-30의 12월31일 목요 위클리 조정 일정은 유지한다. 12월31일부터는 지원 구간 소진을 source failure로 보고한다. 연간 유지보수는 `docs/TECH-DEBT.md`의 2026-10-29 연도별 달력 잔여 항목으로 추적하며 NYSE 달력을 변경하지 않는다.

## Coin Metrics 검증과 공개 범위

[활성 주소 정의](https://docs.coinmetrics.io/network-data/network-data-overview/addresses/active-addresses), [Community 데이터와 라이선스](https://github.com/coinmetrics/data), 실제 API 응답을 대조했다. 활성 주소는 사용자 수가 아니고 거래 건수는 거래소 매매량이 아니다. ETH 수치는 L1 범위다. 가격 방향 신호는 만들지 않는다.

API가 activity metric의 status/status-time을 주지 않으므로 검토 상태나 공표 시각을 생성하지 않는다. `published_at`은 수집 시각이며, `as_of`는 대상 관측 구간 cutoff일 뿐 데이터의 과거 vintage를 뜻하지 않는다. 정정된 과거 값이 조회될 수 있다는 문구를 native/legacy 모두 표시한다. raw 및 파생 지표는 기존 대시보드의 별도 공개·보존 허가를 변경하지 않는다.

`live-check.json`은 실제 read-only 조회로 BTC/ETH 4개 지표와 7일 평균을 확인한 기록이다. API 원문 전체나 EF 기사 본문을 저장하지 않는다. synthetic fixture로 null/음수/소수/초과 자릿수/중복충돌/비연속일/페이지 초과/응답 상한/실패 격리/UTC cutoff를 검사한다.
