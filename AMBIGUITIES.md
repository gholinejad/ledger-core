# AMBIGUITIES

Each entry gives the ambiguity, how I resolved it, and what would change under the other reading.

## Time and ordering

1. **Stream order versus booking day.** E10 is booked on Day 5 but arrives after E9, which is booked on Day 6. The brief says the stream is "replayed in this order".
   **Resolved:** stream order is the processing order. The ledger does not re-sort events. When an event's booked day is already closed, it is processed on the current day and flagged as a late arrival.
   **Other reading:** sort by booked day first. That would hide exactly the problem a real ledger has, which is that events arrive late. It is shown by `tests/test_known_failure.py`.

2. **What "per day" output means once entries can be dated back to earlier days.**
   **Resolved:** each day's block is what the ledger knew and printed at that day's close. Later changes to earlier days appear as `restated` lines and are never edited into the old block. A printed statement is a historical fact.

3. **When a fee is assessed for an earlier day that has just gone negative.** E7 is booked on Day 5 but makes Day 2 negative.
   **Resolved:** fees and accruals are worked out only at the end-of-day close. The fee is posted during the Day 5 close and dated Day 2 ("booked with value_date equal to the day assessed").
   **Other reading:** assess the fee the moment the earlier-dated entry posts. Auth-B would still be declined either way.

4. **Which balance the fee test reads.**
   **Resolved:** all entries dated on or before that day, including fees for earlier days, but excluding that day's own fee. Without that exclusion, a fee could make the balance negative and so justify itself on every re-test, and it could never be reversed. Criterion 1's wording, "before any fee is assessed", supports this reading.

5. **Is a fee refunded when the overdraft that caused it is later undone?** This is the E9 case.
   **Resolved:** yes. I read the fee rule as a condition the ledger must keep true for every day as currently known. After E9, Days 2, 4 and 5 are no longer negative, so those fees are no longer owed, and each is undone with a FEE_REVERSAL entry. Nothing is deleted.
   **Other reading:** fees are final once assessed. That would leave the ledger holding fees for days it now shows as positive, which breaks the rule as written.

6. **The value date of an authorization.** E3 and E8 carry value dates.
   **Resolved:** ignored. A hold is not a ledger entry, so it has no value date in the balance. It reduces the available balance from the moment it is approved.

7. **Which "ledger balance" an authorization is checked against.**
   **Resolved:** all entries dated up to the current business day. There are no future-dated entries in this stream, so this is the same as all posted entries.

## Money

8. **"Three equal instalments" of BHD 10.000.** These cannot be equal at 3 decimals: 10.000 / 3 = 3.333…
   **Resolved:** 3.333, 3.333 and 3.334. The last instalment takes the remainder, so the three sum exactly to 10.000. All three are dated Day 5.

9. **An overdraft fee on a BHD account.** The fee is priced only in AED.
   **Resolved:** no BHD fee is defined. If a BHD account went negative, the close would raise an ERROR rather than invent an FX rate. ACC-002 is never negative in this stream.

10. **The interest base.**
    **Resolved:** the closing ledger balance of each day, including fees. Accrued interest is not part of the base until it is capitalised, so there is no daily compounding. Only positive balances earn interest. The Day 6 accrual is calculated before the capitalisation credit is posted, so interest never earns interest within the window.

11. **The rounding mode for accruals.** The brief only says "rounded".
    **Resolved:** half-even, applied to each day on its own. No figure in this stream is a tie. See NUMBERS.md.

12. **Accruals for earlier days when the balance is restated.**
    **Resolved:** they are recalculated at every close, and the difference is posted as an accrual delta. The capitalised amount is the sum of all accrual records, which equals the sum of the final rounded daily accruals. This is checked by a test.

13. **Is the Day 6 closing balance before or after capitalisation?**
    **Resolved:** after. The INTEREST credit is dated Day 6, so it belongs in the Day 6 closing balance: 285.79, not 285.00.

## Authorizations and settlements

14. **"Authorization ID not present in the ledger."** Authorizations are holds and never appear in the ledger, so read literally, every settlement would be rejected, including Auth-A's. That contradicts criterion 3.
    **Resolved:** I read it as "not present in the authorization log", then rejected the criterion anyway. See REJECTED.md.

15. **A settlement smaller than its hold.** Auth-A is settled at 185.00 against a hold of 200.00.
    **Resolved:** the settled amount is posted, and the whole hold is released, so the 15.00 is never charged. One settlement closes the authorization.
    **Not exercised:** incremental or multiple captures against one authorization.

16. **A settlement larger than its hold.**
    **Resolved:** it is posted and raised as an EXCEPTION. This case is not in the stream.

17. **Settlement against a declined or already-settled authorization.**
    **Resolved:** it is treated like an unknown authorization: force-posted and raised as an EXCEPTION.

18. **Hold expiry.** Auth-B is "never settled inside the window".
    **Resolved:** Auth-B was declined, so it never held anything. No hold TTL is modelled, because the brief gives no expiry period. See the architecture document on authorization lifecycle.

19. **Criterion 5 is conditional ("If Auth-B is approved...").** The condition is never true, because Auth-B is declined.
    **Resolved:** the criterion is accepted as a rule and tested on Auth-A, which is approved. It is not tested on Auth-B.

## Reversals

20. **The value date of a reversal.** E9 is dated Day 2, the same as E7.
    **Resolved:** the reversal uses the value date it is given. If that differed from the original's, the effect would apply from the reversal's own date. A reversal undoes every CREDIT or DEBIT entry of the target event. A second reversal of the same event is refused with an ERROR.

21. **A reversal does not reverse decisions.**
    **Resolved:** E9 reverses money, not the Auth-B decline. The decline was communicated to the merchant on Day 5 and stays DECLINED. See criterion 6 in REJECTED.md.

## Scope

22. **What a "day" is.** These are business days 1 to 6, with no calendar, weekends, holidays or time zone. The end-of-day close runs when the stream moves to a later day, and after the last event.

23. **Duplicate event IDs.** An event ID that has already been seen is ignored with an ERROR. A real system would make this idempotent by key and payload hash; see the architecture document.
