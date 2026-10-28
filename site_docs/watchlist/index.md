# 관심 자산 누적

➡️ [오늘의 관심 자산 영향](daily.md)

## 영향 그룹 안내

- **직접 (Direct)**: 티커/심볼 구조화 매칭 또는 정확한 별칭 일치. 본문·텔레그램에 노출됩니다.
- **관련 (Related)**: 섹터·키워드·매크로 맥락 매칭(직접 자산 일치는 아님). 본문에 맥락으로 노출됩니다.
- **보류 (Uncertain)**: 저신뢰 텍스트 매칭. 진단 블록에만 표시되며 공개 첫인상에는 노출되지 않습니다.
- **제외 (Rejected)**: 짧은 티커 오탐(예: `BTC`↔`BTM`/`BTCS`, `SOL`↔`SLGL`) 억제 기록. 진단 블록에만 표시됩니다.

> 짧은 티커(`BTC`, `SOL` 등)가 오탐을 일으키면 `config/watchlist.json`의 `aliases`에 정확한 표기(`Bitcoin`, `BTC-USD`, `Solana`, `SOL-USD`)를 등록하면 직접 매칭 신뢰도가 올라갑니다.

_관심 자산 영향은 관찰형 정보이며 매매 권유가 아닙니다._

<figure class="investo-watchlist-chart" markdown="0"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 306" role="img" aria-label="관심 자산 누적 매칭"><style>.investo-watchlist-title{fill:#153237}.investo-watchlist-text{fill:#53666b}.investo-watchlist-bar{fill:#006d68}[data-md-color-scheme="slate"] .investo-watchlist-title{fill:#e8f2f2}[data-md-color-scheme="slate"] .investo-watchlist-text{fill:#a9bbc0}[data-md-color-scheme="slate"] .investo-watchlist-bar{fill:#81d9cc}</style><desc>각 자산의 전체 매칭 수는 아래 표에서도 확인할 수 있습니다.</desc><text class="investo-watchlist-title" x="12" y="16" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#111827">관심 자산 누적 매칭</text><text class="investo-watchlist-text" x="12" y="40" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">BTC</text><rect class="investo-watchlist-bar" x="110" y="24" width="208" height="24" fill="#3a8dde" rx="3"/><text class="investo-watchlist-text" x="324" y="40" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">111</text><text class="investo-watchlist-text" x="12" y="70" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">SOL</text><rect class="investo-watchlist-bar" x="110" y="54" width="208" height="24" fill="#3a8dde" rx="3"/><text class="investo-watchlist-text" x="324" y="70" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">111</text><text class="investo-watchlist-text" x="12" y="100" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">ETH</text><rect class="investo-watchlist-bar" x="110" y="84" width="204" height="24" fill="#3a8dde" rx="3"/><text class="investo-watchlist-text" x="320" y="100" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">109</text><text class="investo-watchlist-text" x="12" y="130" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">NVDA</text><rect class="investo-watchlist-bar" x="110" y="114" width="198" height="24" fill="#3a8dde" rx="3"/><text class="investo-watchlist-text" x="314" y="130" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">106</text><text class="investo-watchlist-text" x="12" y="160" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">AAPL</text><rect class="investo-watchlist-bar" x="110" y="144" width="191" height="24" fill="#3a8dde" rx="3"/><text class="investo-watchlist-text" x="307" y="160" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">102</text><text class="investo-watchlist-text" x="12" y="190" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">AMZN</text><rect class="investo-watchlist-bar" x="110" y="174" width="183" height="24" fill="#3a8dde" rx="3"/><text class="investo-watchlist-text" x="299" y="190" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">98</text><text class="investo-watchlist-text" x="12" y="220" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">GOOGL</text><rect class="investo-watchlist-bar" x="110" y="204" width="183" height="24" fill="#3a8dde" rx="3"/><text class="investo-watchlist-text" x="299" y="220" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">98</text><text class="investo-watchlist-text" x="12" y="250" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">MSFT</text><rect class="investo-watchlist-bar" x="110" y="234" width="181" height="24" fill="#3a8dde" rx="3"/><text class="investo-watchlist-text" x="297" y="250" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">97</text><text class="investo-watchlist-text" x="12" y="280" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">기타</text><rect class="investo-watchlist-bar" x="110" y="264" width="360" height="24" fill="#3a8dde" rx="3"/><text class="investo-watchlist-text" x="476" y="280" font-family="Noto Sans KR, Arial, sans-serif" font-size="14" fill="#1f2937">192</text></svg></figure>

| 종목 / 자산 | 매칭 수 | 누적 페이지 |
|-------------|---------|-------------|
| AAPL | 102 | [AAPL.md](AAPL.md) |
| AMZN | 98 | [AMZN.md](AMZN.md) |
| BTC | 111 | [BTC.md](BTC.md) |
| ETH | 109 | [ETH.md](ETH.md) |
| GOOGL | 98 | [GOOGL.md](GOOGL.md) |
| META | 96 | [META.md](META.md) |
| MSFT | 97 | [MSFT.md](MSFT.md) |
| NVDA | 106 | [NVDA.md](NVDA.md) |
| SOL | 111 | [SOL.md](SOL.md) |
| TSLA | 96 | [TSLA.md](TSLA.md) |
