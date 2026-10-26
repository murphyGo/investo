# u184 independent review

2026-10-26. dev-investo Step5.1 review by separate agent `/root/u180_code_review`, read-only.

| Area | Result |
|---|---|
| Correctness | Pass after two fixes |
| Safety / resource lifecycle | Pass within reviewed scope |
| Reliability | Pass after bounded tick and HTML budget fixes |
| Maintainability | Pass |
| Tests | Reviewer Python28 and Node10 passed; root focused Python41 and combined Node39 passed |

High: valid high-precision Decimal rates could stall an unbounded tick loop under default precision28. Fixed with precision96 across rendering and at most12 index-based ticks. Regression uses64-character source decimals; old reproduction now completes with6ticks.

Medium:128events distributed over26days exceeded the existing120KiB HTML cap. Large calendars now render static counts without duplicated previews, and category guidance appears once. Full exact agenda and no-JS links stay intact; old reproduction is104,665bytes. Regressions cover128events across29days with exact and date-only times.

Browser visual inspection also found the SVG hidden property did not hide SVG elements; use the hidden attribute instead. Reset restores keyboard focus to the agenda heading. Final reviewer C/H/M0/0/0; static count-only cells do not claim hidden preview counts.
