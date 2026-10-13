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
    **Resolved:** after. The INTEREST credit is dated Day 6, so it belongs in the printed Day 6 closing balance: 285.79, not 285.00.
    **But the Day 6 fee test and accrual read the balance before capitalisation.** Capitalisation is the last act of the window. If the fee test counted it, a capitalised credit could cancel the Day 6 overdraft that decides the Day 6 accrual, which is part of that same credit. That is circular, and the restatement would stop being idempotent. A second run after capitalisation would change what the first run posted in two ways:
    - It would reverse a Day 6 fee once interest brings Day 6 to zero or above.
    - It would accrue Day 6 interest on the capitalised interest itself. Whenever that changes the rounded Day 6 accrual, the accruals would no longer sum to the capitalised credit. For AED 10,000.00 the Day 6 accrual would go from 4.00 to 4.01.

    For this stream both readings round the same: 285.00 and 285.79 both give 0.11, and ACC-002 gives 0.004 either way. Both print 285.79. The tests are `test_restatement_is_idempotent_after_capitalisation` and `test_accrual_restatement_ignores_the_capitalised_credit`.

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
    **Resolved:** the reversal uses the value date it is given. If that differed from the original's, the effect would apply from the reversal's own date.
    **Scope:** a reversal undoes every money entry the target event caused, matched on the entry's `event` field. That covers CREDIT, DEBIT, SETTLEMENT and FORCE_POST, and includes all three E10 instalments. Reversing a FORCE_POST is the chargeback credit when a dispute is won. Fees and interest are never reversed by hand, because the close owns them.
    **Refused with an ERROR, before the reversal's ID is consumed:**
    - a reversal on a different account from the target's;
    - a second reversal of the same event;
    - a reversal of a reversal;
    - a target that moved no money (a hold) or does not exist;
    - a reversal that carries an amount. A reversal is always full; partial reversals are not supported.

21. **A reversal does not reverse decisions.**
    **Resolved:** E9 reverses money, not the Auth-B decline. The decline was communicated to the merchant on Day 5 and stays DECLINED. See criterion 6 in REJECTED.md.

## Scope

22. **What a "day" is.** These are business days 1 to 6, with no calendar, weekends, holidays or time zone. The end-of-day close runs when the stream moves to a later day, and after the last event.

23. **Duplicate event IDs.** An event ID that has already been seen is ignored with an ERROR. A real system would make this idempotent by key and payload hash; see the architecture document.

24. **Invalid events and a closed window.** The brief's stream has none of these, but a ledger must still decide what happens to them.
    **Resolved:** each of the following is refused with an ERROR before its ID is consumed, so a corrected retry can reuse the ID:
    - a credit, debit, settlement or reversal with a value date before Day 1 or after the processing day (future-dated entries are not supported). Authorizations carry no value date on the ledger (#6), so this rule does not apply to them;
    - a booked day outside Day 1..6;
    - an authorization ID that is missing or already exists;
    - an unknown event type;
    - a non-positive amount on a credit, debit or settlement;
    - a negative authorization. Zero is allowed: it is a card's account-verification check and holds nothing.
    - a credit split into fewer than one part, or into more parts than it has minor units (every instalment must be at least 1 fils);
    - a missing value date on a credit, debit, settlement or reversal;
    - any event that arrives after Day 6 has been capitalised.

    For well-typed events of realistic size nothing raises out of `apply()`. Size is not bounded: a credit split into, say, 2^62 instalments of an equally huge amount would exhaust memory, and a production parser would cap both.
    Python types are not validated, so what happens to a wrongly typed field is unspecified: it may raise, be posted, or be refused by a check it fails to match. An authorization ignores its value date entirely. Type checking belongs to the parser that would build the events.
    An event refused for its content (type, amount, parts, value date, authorization ID, reversal target) still advances the business day to its booked day, because its arrival is a fact about the stream. An event refused for its envelope (duplicate event ID, unknown account, booked day outside the window, window closed) does not move the day.
    An event refused because the window has closed is still kept as a notice in `ledger.notices`. No daily report prints it, because the last report was Day 6's.
