# binance-crypto-market fixture metadata

- Source: Binance public spot 24h ticker endpoint.
- Endpoint shape: `https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT`
- Captured timestamp: synthetic recorded-shape fixture for 2026-05-08 development; not live production data.
- HTTP status represented: 200 OK for JSON responses.
- Access notes: public no-key endpoint; adapter uses shared `retry_get` and per-symbol isolation.
