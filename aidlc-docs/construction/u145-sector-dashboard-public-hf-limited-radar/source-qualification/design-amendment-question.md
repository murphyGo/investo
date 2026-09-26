# u145 Step 0 Design Amendment Question

## Confirmed Live Contract

- `HF_DATA_API_KEY` is valid and masked in GitHub Actions.
- `X-API-Key + daily Parquet` succeeds; bearer fails with 401.
- The documented daily CSV token currently returns 404.
- SPY plus ten sector ETFs passed the source gate; XLRE remains 404/unavailable.
- Each Parquet response is below 249 KiB and 5,954 rows; total input is 2.33 MB.
- Final read-only probe `33578785358` completed in 24 seconds with no raw retention.
- Pages, schedule, Telegram, and adapter/model implementation remain disabled.

## Question 1

How should u145 proceed after the live provider contract drift?

A) Recommended — amend Functional/NFR/Tech Stack contracts for the two-step signed daily
Parquet path, add a pinned sector-workflow-only Parquet reader with no pandas/raw persistence,
then continue to Code Generation Step 1
B) Keep the no-new-dependency design and wait for HF daily CSV to become available before any
implementation
C) Reopen source qualification and choose a different provider/product contract
D) Pause u145 without further changes
X) Other (please describe after the [Answer]: tag below)

[Answer]:
