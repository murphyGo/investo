# u152 선행 관측값 계약 개발

u16147031596 원격 일치 확인 후 시작한 u162의 필수 선행 작업이다.9/28 기존 fixed contracts를 구체 설계로 기록했고,10/03 사용자의 gogo에 따라 이어서 구현했다. 구현 packet 세 개가 남긴 증거를 읽고 부모 resolver와 통합했다. 원래 root dirty 파일과 scratch를 보존했다.

실제 empty payload에서 threshold/source/date 세 current가 통과하는 결함을 먼저 재현했다. 관측 identity/metric·충돌·CFTC 날짜·필드 소유권을 바로잡고 실제 finalizer 테스트로 확인한다. 미지원 신호/출처의 가격 오인, 공급자명의 자산 오인, 출처 전용 펀딩/OI 매칭 P2 네 건을 같은 검토 wave에서 수정하고 독립 재검을 통과했다. fullgate 및 per-unit commit/push 증거는 완료 시 기록한다.

최종 전체5961/472.37s, 집중165/4.01s, 독립66/5.72s+반례14 통과. Ruff/format657, mypy289, 정책4개, strict docs/Material 및 event benchmark p95=137.474ms 통과. 앞선 전체 실행은 교정 중 중단했으며 최종 gate에 포함하지 않는다. 최종 원격 SHA는 후속 u162 시작 audit에서 기록한다.
