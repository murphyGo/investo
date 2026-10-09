# u164 business logic

Normal date resolution grants one run-level snapshot reference. Explicit target-date replay does not. The collector places this optional reference in adapter windows without changing the news/date interval. CoinGecko receives its single batch response, captures UTC receipt time, normalizes each coin independently and accepts live timestamps in the closed six-hour-to-receipt interval. Historical mode uses the existing half-open date window.

Each accepted item retains its real provider as-of, target report date and retrieval reference. Optional numeric values remain absent when unknown or non-finite. The current price survives even if change/volume/cap/high/low is missing. Prompt and public consumers disclose 조회 시점 가격 and actual UTC as-of; consumers do not relabel it as a historical close.

Source registry/name/tier/core membership and six-hour health remain unchanged. Invalid entries do not erase valid siblings; network/parser failures keep the existing source error contract. Candidate historical/independent providers remain outside this implementation.
