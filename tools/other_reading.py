"""Reproduce AMBIGUITIES #3, other reading 2: a closed day is never re-tested.

Each end-of-day close tests the fee and accrues interest for its own day only,
then capitalises at the end of Day 6 as usual. No fee or accrual of an earlier day is restated
(the inherited report still prints the restated balances that back-valued entries cause).

    python3 tools/other_reading.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledger.core import LAST_DAY, Ledger  # noqa: E402
from ledger.money import fmt  # noqa: E402
from ledger.stream import ACCOUNTS, STREAM  # noqa: E402


class OwnDayOnly(Ledger):
    def close_day(self):
        d = self.day
        first_entry, first_accrual = len(self.entries), len(self.accruals)
        for account, ccy in self.ccy.items():
            self._restate_fee(account, ccy, d, f"EOD{d}")      # fee test for today only
            self._restate_accrual(account, d)                  # accrual for today only
        if d == LAST_DAY:
            for account in self.ccy:
                total = sum(a.amount for a in self.accruals if a.account == account)
                if total:
                    self._post(account, "INTEREST", total, LAST_DAY, f"EOD{d}")
        report = self._report(d, first_entry, first_accrual)
        self.reports.append(report)
        self.day += 1
        return report


if __name__ == "__main__":
    ledger = OwnDayOnly(ACCOUNTS)
    for event in STREAM:
        ledger.apply(event)
    while ledger.day <= LAST_DAY:
        ledger.close_day()
    a1 = "ACC-001"
    fees = [(e.kind, fmt(-e.amount, "AED"), f"value Day {e.value_day}") for e in ledger.entries
            if e.account == a1 and e.kind.startswith("FEE")]
    interest = sum(e.amount for e in ledger.entries if e.account == a1 and e.kind == "INTEREST")
    print("fees:", fees)
    print("Day 5 closing:", fmt(ledger.reports[4]["accounts"][a1]["closing"], "AED"))
    print("Day 6 closing:", fmt(ledger.reports[5]["accounts"][a1]["closing"], "AED"), "interest", fmt(interest, "AED"))
