# fsc-krx-stock-price fixture metadata

- Source: FSC/data.go.kr `금융위원회_주식시세정보`
- Dataset page: https://www.data.go.kr/data/15094808/openapi.do
- Endpoint shape: `https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo`
- Captured timestamp: synthetic recorded-shape fixture for 2026-05-08 development; not live production data.
- HTTP status represented: 200 OK for normal and empty-row responses.
- API key handling: fixtures use no real service key. Tests inject `INVESTO_KRX_SERVICE_KEY=test-service-key` and assert it does not leak into raised `SourceFetchError`.
- Fair access notes: adapter uses the shared `retry_get` helper with bounded timeout, one retry, identity encoding, and max response-size enforcement.
