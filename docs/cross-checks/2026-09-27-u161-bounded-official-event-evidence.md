# u161 요구사항 cross-check

2026-09-27. 고정 qualification·NF4/NF8·typed evidence 계약을 기존 pipeline과 대조한다. 최종 전체 회귀5888개(464.69초), Ruff/format655개, mypy289개, 정책4개, strict MkDocs와 Material gate가 통과했다. 독립 검토에서 확인한 P2는 같은 review wave에서 교정했다.

| 기준 | 확인 근거 |
|---|---|
| AC-161.1 기존 소스 진단 | 공식 discovery와 실제 bounded probe: CNBC403 blocked 유지. FSC HTTP302 및 pubDate 부재를 독립 재현하고 같은 HTTPS/date-only 수리 후 실제7개를 확인했다. |
| AC-161.2 qualification 경계 | 명시적 네 source manifest: FOMC/Fed speech/CFTC qualified, SEC blocked. 실제 feed의 직접 링크·rights·host/path/MIME·unique selector·live SHA를 확인한 뒤 Stage C를 구현했다. off/shadow/unqualified의 body HTTP0 통합 회귀. |
| AC-161.3 긴 근거의 실제 전달 | `test_event_enrichment.py`의 char400–421 사실이 실제 adapter/collector/GenerationInput/Stage1/Stage2/봉인 본문·DTO까지 전달된다. 미선정 배경/1200자 이후/타시장/실패 source 근거는 제외된다. |
| AC-161.4 고정 자원 상한 | EnrichmentPolicy와 helper의 6요청/동시2/요청8초/총20초/decoded500KiB/source2/excerpt1200 및 redirect/SSRF negative. 최종 focused 결과는 validation에 기록한다. |
| AC-161.5 실패와 시점 | 실제 CollectStage의 403/selector loss는 원 item와 source 성공을 보존하고 별도 unavailable outcome을 남긴다. typed revision만 갱신하며 source publication을 사건 시각으로 바꾸지 않는다. |
| AC-161.6 공개 데이터·성능 | raw live bodies는 ignored private `.tmp`에만 있다. public artifact는 제한된 metadata/hash와 synthetic fixture다. NFR-008 gate 및 end-to-end 미측정/DEBT-090 유지 상태를 기록한다. |

합성 empty baseline은 사건 중요도 검사의 독립 fixture 입력이며 운영 첫 실행의 포착률로 간주하지 않는다. source별 단발 qualification과 FSC 수리 결과는 scheduled shadow/운영 게시 완료의 대체 증거가 아니다. FR-023 전체와 다른 유닛 운영 gate는 변경하지 않는다.
