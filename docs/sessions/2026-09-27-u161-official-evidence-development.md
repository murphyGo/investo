# u161 공식 사건 근거 개발

사용자 승인 순서의 다섯 번째 유닛이다. u160 `79b9f03981a2f26ef74126e4bb86928a9b118950`를 작업 브랜치에 전달하고 exact remote SHA를 확인한 뒤 시작했다. 원래 root의 dirty 파일은 보존한다.

실제 source qualification을 먼저 수행해 공식 본문 세 범위를 확인했다. CNBC 피드/SEC 본문은403 blocked다. FSC는 같은 제공자의 HTTPS와 date-only fallback으로 수리하고 단발 실제 응답7개를 확인했다. 긴 기존 feed 설명은 명시적 v2 clock에서만 typed evidence에 추가한다. 본문 보강은 모델 정책·manifest·기존 streaming retry helper와 aggregate deadline으로 제한한다.

실제 생성/봉인 통합9개, 기존 source68개, FSC/feed16개, CLI10개, 기존 사건/뉴스window/최종화113개와 mypy289개가 초기 검증에서 통과했다. 2026-09-28 최종 전체5888개(464.69초), focused104개, Ruff/format655개, mypy289개, 정책4개, strict docs7.08초와 Material gate를 통과했다. 선정/검증 benchmark p95는129.072ms(기준200ms)다. 독립 검토 P2 다섯 건을 같은 wave에서 교정했다. 운영 활성화·scheduled shadow·외부 알림은 수행하지 않으며 DEBT-090을 닫지 않는다.
