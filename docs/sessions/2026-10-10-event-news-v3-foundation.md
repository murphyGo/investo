# Event/news v3 foundation development — 2026-10-10

사용자 문서 작성·구조 개편·커밋/푸시와 별도 워크트리 개발 지시에 따라 진행했다. 문서 기준838bed60은 이미 main에 푸시됐고, 개발은 `.tmp/news-event-v3-dev-20261010`의 `codex/news-event-v3-dev-20261010`에서 수행했다. 기존 root dirty work와 concurrent u145 UI 변경을 보존했다.

## Delivered code

- `6ba3a094`: u167 private context/time/ref/support models, source factory, exact UTF-8 budgets, Stage1 CLI replacement, deterministic shadow handoff와 u168 canonical identity/fact delta/shared story DTO/remote hash-only ledger foundation.
- `0de9d9d2857ca0bd77d10fa5a750a30286caec15`: component metadata authority, affirmative same-slot correction, multi-actor/entity provenance 회귀 수정.

Source status·value·metric·unit·period를 해당 source fields와 exact refs에 결속한다. required actual은 typed actual slot을 보존한다. 의미·반응 근거가 identity/fact refs와 독립적으로 보호 버퍼에 도달하며 필수→meaning/reaction→background 순으로 예산을 적용한다. source 시점과 publication/received 시점을 분리하고 품질 부족을 독립 축으로 기록한다.

Canonical facts는 NFKC/공백/숫자 thousands separator만 정규화한다. metric/unit/period/status가 다르면 다른 fact다. hash-only FactSlotReceipt로 이전 actual과의 충돌을 확인하며 명시 정정이 없는 상충 값은 unknown/conflict다. source-owned occurrence 기간, raw duplicate 분리, 늦은 공식 alias의 기존 ID 유지, 누적 fact history, alias-only freshness 유지와 stable serialization을 검증했다. story models만 선언했고 reducer를 발급하지 않는다.

## Verification

- 최신 main ea402465에 rebase하며 두 append-only audit 이력을 보존했다.
- 정확한 코드0de9d9d2: **6774 tests PASS873.04s**.
- foundation/legacy/concurrent sector UI focused:170PASS215.07s.
- 최종 독립 foundation 검토:81PASS/P1-P2=0/mypy307PASS.
- Ruff/format719/mypy307,4policyguards,strictMkDocs7.64s,Material/built-HTML PASS.
- 96문서 buffer 측정10회: Stage1 21689bytes/Stage2 7674bytes,median10.463ms/p95 sample10.821ms.5000record serialization은1MiB초과를명시거절(88.423ms). offline preparation만 측정했고 production/runtime p95를 주장하지 않는다.

## Remaining work

u167foundation8/8;u168foundation5/8. u168 Step6–8의 native E5 survivor/combined CAS 연결은 u169 이후 진행한다. u169 전체 문서·단일 finalizer, u170 story reducer, u171 reader surfaces, u172 real human/market acceptance와 genuine scheduled observations, u173 official source qualification은 미완료다. registry 주체 correction source binding을 제공하지 못하면 보수적으로 거절한다.

기본 schema2, v3 preview/active capabilityFalse, production metadata write0을 유지했다. 기존 두 LLM 단계 외 추가 단계나 HTTP 호출을 도입하지 않았다. 실제 사람 수용·실제 운영·source권한·legacycutover 완료를 offline test로 대신하지 않는다. DEBT-090은 변경하지 않았다.
