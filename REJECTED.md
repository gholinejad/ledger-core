# REJECTED

## Part A: acceptance criteria I refused

There are eight criteria. I accept three (1, 3 and 5) and refuse five (2, 4, 6, 7 and 8). Every refusal has a test in `tests/test_ledger.py` that asserts what the ledger actually does.

| # | Criterion (summary) | Verdict |
|---|---|---|
| 1 | Day 2 closing balance is −370.00 at the end of Day 5, before fees | **Accepted.** 250.00 − 620.00 = −370.00. |
| 2 | E7 causes exactly one fee, on Day 2 | **Rejected** |
| 3 | The Auth-A settlement must be accepted | **Accepted** |
| 4 | Unknown authorization: reject, and funds must not leave | **Rejected** |
| 5 | An approved Auth-B hold reduces available balance but not ledger balance | **Accepted** as a rule. Note that its premise is false: Auth-B is declined. |
| 6 | After E9, all balances and fees return to their pre-E7 values | **Rejected** |
| 7 | Each BHD instalment is 3.334 | **Rejected** |
| 8 | If accruals do not sum to the capitalised total, discard the remainder | **Rejected** |

### Criterion 2: "E7 causes exactly one overdraft fee, on Day 2"

E7 does not touch only Day 2. It is dated Day 2, so it lowers the closing balance of every day from Day 2 onward. Each of those days must be tested again:

- Day 2: −370.00 → fee
- Day 3: −395.00 + 400.00 = +5.00 → no fee
- Day 4: 5.00 − 185.00 − 180.00 = −360.00 → fee
- Day 5: −385.00 → fee

E7 causes **three** fees (Days 2, 4 and 5), assessed at the Day 5 close. Without the force-posted E6, Day 4 would be −180.00 and still three fees. The criterion counts only the day the entry is dated, not the days it carries forward into. Test: `test_c2_e7_causes_three_fees_not_one`.

**It is wrong under other reading 2 too.** Suppose a closed day is never re-tested: each close tests the fee and accrues interest for its own day only (AMBIGUITIES #3, reproduced by `python3 tools/other_reading.py`). Then E7 causes exactly one fee, but it is dated **Day 5**, not Day 2: Day 5 closes at −360.00, and Day 6 at 260.67 with 0.67 interest. There is no reading under which the criterion holds: under every reading Day 5 is −335.00 before any fee, so at least the Day 5 test is negative.

### Criterion 4: "Any settlement referencing an authorization ID not present in the ledger must be rejected and the funds must not leave the account"

The criterion is wrong for three reasons.

1. **It contradicts itself.** Authorizations are holds and are never in the ledger. Read literally, it would reject Auth-A as well, which contradicts criterion 3.
2. **"The funds must not leave the account" is not under the issuer's control.** A settlement means the card scheme has already paid the merchant and is debiting the issuer. Refusing to post the debit does not stop the money leaving the bank. It only moves the loss off the customer's account and into an unreconciled suspense position. Offline and force-posted transactions (transit, in-flight, below-floor-limit) legitimately arrive with no authorization.
3. **The correct response is to post it and dispute it.** The debit is posted as a `FORCE_POST`, so the customer's ledger matches what the scheme settled. An `EXCEPTION` is raised for chargeback review. If the dispute is won, a reversal credit follows.

Test: `test_c4_unmatched_settlement_is_posted_and_raised`.

### Criterion 6: "After E9, all balances and fees return to their pre-E7 values"

The net figures do return. The ledger's state does not.

- **Fees are not un-assessed.** There are still three FEE entries, and three FEE_REVERSAL entries undo them. The ledger is append-only, so its history now holds six fee records that did not exist before E7. A fee count, revenue report or customer statement taken from that history differs from the pre-E7 one.
- **Statements already issued stay issued.** The Day 5 close printed −410.00. A Day 6 reversal corrects that figure but does not make the earlier print untrue.
- **Authorization decisions are not reversible.** Auth-B was declined on Day 5 because of E7. The merchant and the cardholder were told "declined" at that moment. E9 cannot retroactively approve a card transaction. Before E7, the same request would have been approved (available 285.00 − 90.00 ≥ 0). So the authorization state after E9 is **not** what it would have been without E7.
- **Interest is only right because of restatement.** The accruals return to their pre-E7 values only because every close re-evaluates them. A system that never revisited accruals after the Day 5 close would capitalise 0.21 (Day 1 0.10 + Day 6 0.11) instead of 0.79.

Test: `test_c6_after_e9_net_balances_return_but_history_and_auth_do_not`.

### Criterion 7: "The three BHD instalments in E10 must each be BHD 3.334"

3 × 3.334 = 10.002, which is not 10.000. That would credit 0.002 BHD that was never received. Three equal instalments of 10.000 cannot be represented at 3 decimals. The instalments are **3.333, 3.333 and 3.334**, with the remainder on the last one, and they sum exactly to 10.000. Test: `test_c7_instalments_are_3333_3333_3334`.

### Criterion 8: "If the rounded daily interest accruals do not sum to the capitalized total, the remainder is discarded"

This contradicts a non-negotiable rule, which says the rounded daily accruals must sum **exactly** to the capitalised total. Discarding a remainder is the very mismatch that rule forbids, and it would also be an unexplained gain or loss in the books. In this design the capitalised amount is defined as the sum of the accrual records, so a remainder cannot exist: ACC-001 is 0.79 and ACC-002 is 0.008. Test: `test_c8_daily_accruals_sum_exactly_to_capitalised`.

## Part B: approaches abandoned mid-build

Both were abandoned while the core was being written, before its first commit (`d7475a7`). The commit history therefore does not show them, and this section is their only record.

1. **Reversal tracking through a side index.** The first version kept a dictionary of "event → events that reversed it" outside the entry log. I replaced it with a `reverses` field on the REVERSAL entry itself. Keeping the fact in a second structure meant two sources of truth, and the side index was mutable state inside an append-only design.

2. **Comparing "restated" against the day's original print.** The first report compared each earlier day's balance with the figure printed at that day's own close. On Day 6 that hid the Day 2 correction: it went 250 → −395 → 250, and the Day 6 value matched the original 250, so nothing showed. The report now compares against the figure *last printed*, so every correction a reader saw is visibly undone.

## Part C: approaches considered at design time and not built

1. **Rejecting unmatched settlements, as criterion 4 asks.** Not built, for the reasons above.

2. **Fees as final once assessed.** This is simpler, since it needs no FEE_REVERSAL. It was dropped because after E9 the ledger would hold fees for days it shows as positive, which contradicts the fee rule.

3. **Re-sorting the stream by booked day.** This would make the Day 5 statement "correct". It was dropped because it reads the future: on Day 5, the ledger cannot know E10 exists. The failing test keeps this visible instead of hiding it.

4. **Cumulative rounding of interest.** Each day's accrual would be round(cumulative exact) − round(previous cumulative exact). This still satisfies "rounded daily accruals sum exactly to the total" and removes the drift (it would pay 0.80, not 0.79). It was not adopted for two reasons. First, the brief says the daily accruals are rounded, which most naturally means each day on its own. Second, under cumulative rounding a back-dated change to Day 2 would also change the accruals of every later day, even days whose balance did not change. That makes the restatement noisier and harder to audit. I document the 0.01 cost in NUMBERS.md instead.

5. **Storing amounts as Decimal.** Integer minor units were chosen instead. With integers, every addition is exact by construction, and rounding happens only at the one place a rate is applied.
