# In-Memory Account Ledger Core

An in-memory, append-only ledger that replays the six-day event stream and prints, for each day, the closing ledger balance, fee assessments, authorization states and errors. Python 3.10+, standard library only. It has no web layer, persistence or database.

## Run

```bash
python3 replay.py                          # per-day report
python3 -m unittest tests.test_ledger -v   # 23 tests, all pass
python3 -m unittest -v                     # 24 tests: 1 fails on purpose (tests/test_known_failure.py)
```

## Reading the output

Each `=== Day N close ===` block is what the ledger printed when it closed day N, using only what it knew at that point.

| Line | Meaning |
|---|---|
| `closing ledger` | Sum of all entries with value date ≤ N. Holds are excluded. On Day 6 this includes the capitalised interest. |
| `available` | The ledger balance minus active authorization holds. |
| `restated Day k closing X -> Y` | An entry dated back to an earlier day k has changed that day's closing balance since it was last printed. Nothing is edited: the new figure comes from new entries. |
| `fee assessed / fee reversed` | A FEE or FEE_REVERSAL entry posted by this close. `value Day k` is the day the fee belongs to. |
| `accrual Day k ±x` | An interest accrual memo, or a correction to an earlier one. Accruals are not ledger entries until they are capitalised at the end of Day 6. |
| `authorizations` | The current state of every authorization, with the event that set it and the reason. |
| `errors and exceptions` | `ERROR`: rejected, nothing posted. `EXCEPTION`: posted, needs ops review. `WARNING`: processed but unusual. |
| `note` | Informational, for example "back-valued to Day 2". |

## Key results

| | ACC-001 (AED) | ACC-002 (BHD) |
|---|---|---|
| Day 5 close | −410.00 (three fees: value Days 2, 4 and 5) | 0.000 (E10 has not arrived yet) |
| Day 6 close | 285.79 (fees reversed after E9; interest 0.79) | 10.008 (instalments 3.333 + 3.333 + 3.334; interest 0.008) |
| Auth-A | APPROVED on Day 2 → SETTLED on Day 4 at 185.00 | |
| Auth-B | DECLINED on Day 5: available would be −425.00 | |
| Auth-Z | No authorization. Force-posted 180.00 and raised as an EXCEPTION | |

## Design in five lines

1. **Money** is stored as integer minor units (fils). Decimal is used only to apply the interest rate, and the result is rounded half-even straight back to an integer.
2. There are **three append-only logs**: ledger `entries`, interest `accruals` (memos) and `auth_log` (state transitions). All records are frozen dataclasses. A state is always the latest transition; no record is ever edited.
3. **Holds are not ledger entries.** Available balance = ledger balance − holds of APPROVED authorizations.
4. **The end-of-day close re-evaluates every day of the window, oldest first, with what is now known.** For each day it works out the fee and accrual that are owed and posts only the difference, as FEE / FEE_REVERSAL entries or accrual deltas. Entries dated back to an earlier day are handled this way, never by editing.
5. **Stream order is processing order.** An event whose booked day is already closed, such as E10, is processed on the current day and flagged as a late arrival.

## Files

- `ledger/money.py`: minor units, rounding, instalment split
- `ledger/core.py`: the ledger, event handlers and end-of-day close
- `ledger/stream.py`: accounts and the event stream
- `replay.py`: runs the stream and prints the per-day report
- `tests/test_ledger.py`: every acceptance criterion, tested for or against, plus invariants
- `tests/test_known_failure.py`: the one annotated failing test
- `NUMBERS.md`, `AMBIGUITIES.md`, `REJECTED.md`, `WORKLOG.md`
