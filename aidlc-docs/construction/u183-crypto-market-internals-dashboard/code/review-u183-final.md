# u183 independent code review — final

작성일: 2026-10-25. 별도 reviewer. 현재 확인한 미해결 **Critical 0 / High 0 / Medium 0**.

전체 초기 scope·protocol 적용·원천 문서 대조·47개 직접 실행 결과 및 운영 한계는 [review-u183-initial.md](review-u183-initial.md)에 기록되어 있다. 이번 후속 검토는 DeFi의 unknown clock 분류 보정과 두 clock regression에 한정한다.

## 마지막 보정 확인

`valid_crypto_metric()`의 DeFi source-role gate는 알려진 시각에 collection_window 및 source_updated_at=None을 계속 요구한다. precision=unknown인 경우에만 source_response/unknown 및 source_updated_at=None을 의미상 허용한다. 이어지는 selection gate가 이 관찰을 time_unknown으로 분류하여 숫자를 공개하지 않는다. 원천 timestamp를 만들거나 숫자 오류로 잘못 분류하지 않는다. 다른 source role을 provider update로 재명명하는 기존 negative 경계도 유지된다.

해당 코드와 회귀 assertion을 읽었고 reviewer가 직접 다음 두 테스트를 실행했다.

```text
.venv/bin/python -m pytest tests/unit/orchestrator/test_crypto_insights_projection_u183.py::test_unknown_collection_clock_is_unavailable_with_time_reason tests/unit/orchestrator/test_crypto_insights_projection_u183.py::test_known_source_clock_roles_cannot_be_relabelled_as_provider_updates -q
2 passed in 0.80s
```

현재까지 검토 범위에서 새 Critical/High/Medium finding은 없다. 초기 core47 passed in 4.89s는 그 실행 시점의 증거로 유지하며, 마지막 수정 뒤 전체48개를 reviewer가 다시 실행했다고 표현하지 않는다. 최신 lazy attribution 보강은 초기 보고서에 적힌 read-only 코드 확인 범위를 따른다.

실제 source 권리 허가·전체 regression/static/resource/browser 결과·production/private pin/Pages/activation 및 scheduled 운영 수용은 lead의 별도 증거와 구분하며 이 보고서로 완료되지 않는다. source/test 수정, commit/push/배포 없이 보고서만 작성했다.

## 전체 회귀 중 DST round-trip PBT 후속 검토

기존 `tests/unit/models/test_roundtrip.py` helper의 assertion 변경과 imaginary/fold 시각 세 건을 좁게 검토했다. `type(model).model_validate_json()` 후 JSON-visible 전체 필드가 원래 `model_dump(mode="json")`과 같은지를 비교하므로 값·필드·직렬화된 datetime offset 보존을 계속 검사한다. timezone 생성 전략은 기존의 광범위한 IANA timezone 및 imaginary/ambiguous 시각 생성을 유지한다. 명시적인 imaginary 및 fold=0/fold=1 회귀는 UTC instant도 추가로 비교한다. 따라서 문서에 명시한 JSON 보존 계약을 약화하는 수정으로 판단하지 않는다. JSON에 들어 있지 않은 IANA timezone 객체 identity를 보존한다는 요구를 새로 추가하거나 제품 clock 처리를 바꾸지 않는다.

reviewer가 `git show HEAD:src/investo/models/items.py`를 별도 ModuleType으로 읽어 현재 모델과 각각 같은 세 입력을 비교했다. 두 버전 모두 세 입력에서 `model_equal=False`, `json_equal=True`, `utc_equal=True`를 직접 재현했다. 입력은 America/Boise의 2024-03-10 02:00 imaginary 및 2024-11-03 01:30의 두 fold다. 따라서 이 경계는 u183 제품 변경 전 모델에도 존재한다.

공용 helper가 사용되는 기존 public model PBT 전체 파일도 직접 실행했다.

```text
.venv/bin/python -m pytest tests/unit/models/test_roundtrip.py -q
9 passed in 2.29s
```

이 후속 검토의 확정 미해결 C/H/M은 계속 0/0/0이다. 이 실행을 실패 shard 전체 또는 전체7천여 테스트 재실행 성공으로 확대하지 않으며, 해당 broader 회귀 결과는 lead가 별도로 기록한다. reviewer는 test/product 코드를 수정하지 않았다.
