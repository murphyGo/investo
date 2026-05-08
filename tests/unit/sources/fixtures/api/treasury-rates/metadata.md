# treasury-rates fixture metadata

- Source: U.S. Treasury daily treasury par yield curve rates XML.
- Dataset page: https://home.treasury.gov/resource-center/data-chart-center/interest-rates
- Endpoint shape: `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=YYYY`
- Captured timestamp: synthetic recorded-shape fixture for 2026-05-08 development; not live production data.
- HTTP status represented: 200 OK for XML response.
- Access notes: public no-key endpoint; adapter uses shared `retry_get`.
