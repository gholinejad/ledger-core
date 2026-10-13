# NUMBERS

The first section lists every constant in the code and why it has that value rather than, say, half of it. The second section derives every figure the replay prints, so each one can be checked by hand.

## Constants

| Constant | Value | Why this value, and not half of it |
|---|---|---|
| `OVERDRAFT_FEE["AED"]` | `2500` fils (AED 25.00) | Set by the brief. It is stored in fils so the arithmetic is exact. Half (1250) would be a different fee policy, not a rounding choice. No BHD fee is defined, because the brief prices the fee only in AED and converting it would need an FX rate the brief does not give. |
| `DAILY_RATE` | `0.0004` | 0.04 % = 0.04 / 100 = 0.0004. Mis-reading the percentage is the classic error: 0.004 is ten times too high, and half (0.0002) would be 0.02 %. The rate applies to the day's closing balance and does not compound within the window. |
| `PRECISION` | AED 2, BHD 3 | These are the ISO 4217 minor units (BHD uses fils at 1/1000). Using 2 for BHD would lose the third decimal: 0.004 BHD of interest would round to 0.00. |
| Rounding unit | 1 fil | It is the smallest amount that can actually be posted. Any rate result is rounded to it immediately. |
| Rounding mode | `ROUND_HALF_EVEN` | It is unbiased on ties, so over many accounts the halves do not all go one way. No figure in this stream hits a tie (0.114 and 0.26 are not ties), so HALF_UP would give identical output here. That is documented so nobody believes the mode was tested by this data. |
| Overdraft test | `balance < 0` | "Negative" excludes zero. A balance of exactly 0.00 is not overdrawn. |
| Authorization test | `available − amount >= 0` | "At or above zero" includes zero. An authorization that leaves exactly 0.00 available is approved. |
| Instalment split | `divmod`; the remainder goes to the last instalment | 10000 // 3 = 3333 with remainder 1, giving 3.333, 3.333, 3.334. The last instalment is the conventional "balancing" one. |
| Restatement horizon | The whole window (Day 1 to the current day) | E9 arrives on Day 6 and is dated back to Day 2, four days earlier. A horizon of half the window (3 days) would never re-test Day 2, and the Day 2 fee would never be reversed. A production system bounds this horizon; see the architecture document. |
| Window | Days 1 to 6 | Set by the brief. Events booked after Day 6 are refused. Interest is capitalised at the Day 6 close. |

## Every printed figure, derived

### ACC-001 (AED). Fil amounts in brackets.

| Day | What happens | Closing balance |
|---|---|---|
| 1 | E1 +1200.00, E2 −950.00 | **250.00** |
| 2 | E3 Auth-A hold of 200.00. Available = 250.00 − 200.00 = 50.00 ≥ 0, so approved. The ledger is unchanged. | **250.00** (available 50.00) |
| 3 | E4 +400.00 | **650.00** (available 450.00) |
| 4 | E5 settles Auth-A at 185.00 and releases the hold of 200.00. The 15.00 difference is never charged. E6 has no authorization, so 180.00 is force-posted. 650 − 185 − 180 = | **285.00** |

Daily accruals as printed on Days 1–4: 250.00 × 0.0004 = 0.10, then 0.10, then 650.00 × 0.0004 = 0.26, then 285.00 × 0.0004 = 0.114, which rounds to 0.11.

**Day 5.** E7 debits 620.00, dated back to Day 2.
- Before any fee, Day 2 closes at 250 − 620 = **−370.00**. This is acceptance criterion 1.
- E8 (Auth-B, 90.00): the ledger balance at that moment is 250 − 620 + 400 − 185 − 180 = −335.00, so available after the hold would be −425.00. Auth-B is **declined**.
- The Day 5 close re-tests every day, oldest first:

| Day | Balance before that day's own fee | Fee? | Closing balance |
|---|---|---|---|
| 1 | 250.00 | no | 250.00 |
| 2 | −370.00 | yes, 25.00 | −395.00 |
| 3 | −395 + 400 = 5.00 | no (5.00 is not negative) | 5.00 |
| 4 | 5 − 185 − 180 = −360.00 | yes, 25.00 | −385.00 |
| 5 | −385.00 | yes, 25.00 | **−410.00** |

Three fees are posted, so criterion 2 ("exactly one") is wrong. The Day 2 fee is what keeps Day 3 at +5.00 instead of +30.00, and Day 3 still does not go negative. Accruals: Days 2–5 now owe 0. Day 3 would be 5.00 × 0.0004 = 0.002, which rounds to 0.00. So the deltas are −0.10, −0.26 and −0.11.

**Day 6.** E9 credits 620.00, dated back to Day 2. E10 arrives late.
- The Day 6 close re-tests every day. Day 2 before its own fee is 250.00, so the fee is no longer owed: a FEE_REVERSAL of 25.00 is posted. Day 3 is 650.00. Days 4 and 5 are 285.00, so both fees are reversed.
- Accruals now owed: 0.10 + 0.10 + 0.26 + 0.11 + 0.11 + 0.11 = **0.79**. That total is posted as a single INTEREST credit dated Day 6.
- Closing balance: 285.00 + 0.79 = **285.79**.

### ACC-002 (BHD)

- E10: 10.000 is split into 3.333 + 3.333 + 3.334 = 10.000, all dated Day 5. It arrives after E9, so it is processed during Day 6. The Day 5 closing balance printed on Day 5 was 0.000 and is restated to 10.000.
- Accruals: Day 5 is 10.000 × 0.0004 = 0.004, and Day 6 is 0.004, for a total of **0.008**, capitalised on Day 6.
- Closing balance on Day 6: **10.008**.

### A known rounding cost (accepted, not fixed)

Per-day rounding pays ACC-001 0.79. Applying the rate to the exact daily amounts and rounding once would give 0.10 + 0.10 + 0.26 + 0.114 × 3 = 0.802, which rounds to 0.80. The customer receives 0.01 less. Each day's rounding error is at most ±0.005, so over n days the total can drift by up to n × 0.005. See REJECTED.md (cumulative rounding).
