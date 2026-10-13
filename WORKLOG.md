# WORKLOG

Times are local (UTC+03:00). AI tools were permitted; I worked with Claude (Claude Code) as a pair: I set the decisions, it drafted code and text, I reviewed and ran everything. Entries are written as the work happened.

## 2026-10-13

- **15:10** Read the brief. Noted at once: E10 is booked Day 5 but arrives after E9 (Day 6) in the stream, E7 and E9 are back-valued to Day 2, and "three equal instalments" of BHD 10.000 is impossible at 3 decimals.
- **15:20** Worked the numbers by hand for ACC-001 before writing code (Day 2 after E7 = -370.00; Auth-B must be declined because E7 lands first). Decided: integer minor units, append-only entry list, end-of-day close that re-evaluates every past day so back-valued entries are handled by compensating entries, never edits.
- **15:35** Repo created. Money module first: integer minor units, half-even rounding only where a rate is applied, remainder-to-last split.
