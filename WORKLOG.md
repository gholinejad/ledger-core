# WORKLOG

Times are local (UTC+03:00). AI tools were permitted; I worked with Claude (Claude Code) as a pair: I set the decisions, it drafted code and text, I reviewed and ran everything. Entries are written as the work happened.

## 2026-10-13

- **before 15:35** Read the brief. Noted at once: E10 is booked Day 5 but arrives after E9 (Day 6) in the stream, E7 and E9 are back-valued to Day 2, and "three equal instalments" of BHD 10.000 is impossible at 3 decimals.
- **before 15:35** Worked the numbers by hand for ACC-001 before writing code (Day 2 after E7 = -370.00; Auth-B must be declined because E7 lands first). Decided: integer minor units, append-only entry list, end-of-day close that re-evaluates every past day so back-valued entries are handled by compensating entries, never edits.
- **15:35** Repo created. Money module first: integer minor units, half-even rounding only where a rate is applied, remainder-to-last split.
- **15:50** Core ledger: three append-only logs (entries, accrual memos, auth transitions). End-of-day close re-evaluates every day of the window oldest-first and posts only the difference (FEE / FEE_REVERSAL, accrual delta). Unmatched settlement is force-posted and raised as an exception rather than rejected. Replay prints the per-day report; numbers match my hand calculation (Day 5 close -410.00, Day 6 close 285.79, ACC-002 10.008).
