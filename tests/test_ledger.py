"""Acceptance tests. Each criterion from the brief is either asserted (accepted)
or asserted *against* (rejected, see REJECTED.md).

    python3 -m unittest tests.test_ledger -v
"""
import dataclasses
import unittest

from ledger.core import DECLINED, SETTLED, APPROVED, Event, Ledger
from ledger.money import split_evenly
from ledger.stream import ACCOUNTS, STREAM
from replay import run

A1, A2 = "ACC-001", "ACC-002"


def replay_until(event_id: str) -> Ledger:
    """Apply the stream up to and including event_id, without closing that day."""
    ledger = Ledger(ACCOUNTS)
    for ev in STREAM:
        ledger.apply(ev)
        if ev.id == event_id:
            return ledger
    raise AssertionError(event_id)


def kinds(ledger: Ledger, kind: str, account: str = A1):
    return [e for e in ledger.entries if e.kind == kind and e.account == account]


class AcceptedCriteria(unittest.TestCase):
    def test_c1_day2_closing_after_e7_before_any_fee_is_minus_370(self):
        ledger = replay_until("E8")              # end of Day 5 events, close not yet run
        self.assertEqual(kinds(ledger, "FEE"), [])
        self.assertEqual(ledger.balance(A1, 2), -37000)

    def test_c3_auth_a_settlement_accepted_and_hold_released(self):
        ledger = replay_until("E5")
        self.assertEqual(ledger.auth_state("Auth-A").state, SETTLED)
        self.assertEqual([e.amount for e in kinds(ledger, "SETTLEMENT")], [-18500])
        self.assertEqual(ledger.active_holds(A1), 0)  # the unused 15.00 is released, not kept

    def test_c5_approved_hold_moves_available_not_ledger(self):
        ledger = replay_until("E3")              # Auth-A is the approved hold in this stream
        self.assertEqual(ledger.auth_state("Auth-A").state, APPROVED)
        self.assertEqual(ledger.balance(A1, 2), 25000)
        self.assertEqual(ledger.available(A1), 5000)

    def test_c5_premise_auth_b_is_declined(self):
        # E7 lands before E8, so available is negative when Auth-B arrives.
        self.assertEqual(run().auth_state("Auth-B").state, DECLINED)


class RejectedCriteria(unittest.TestCase):
    def test_c2_e7_causes_three_fees_not_one(self):
        ledger = replay_until("E8")
        ledger.close_day()                       # Day 5 close
        fee_days = [e.value_day for e in kinds(ledger, "FEE")]
        self.assertEqual(fee_days, [2, 4, 5])    # Day 3 is +5.00, so no fee there

    def test_c4_unmatched_settlement_is_posted_and_raised(self):
        ledger = replay_until("E6")
        self.assertEqual([e.amount for e in kinds(ledger, "FORCE_POST")], [-18000])
        self.assertTrue(any(n.source == "E6" and n.level == "EXCEPTION" for n in ledger.notices))

    def test_c6_after_e9_net_balances_return_but_history_and_auth_do_not(self):
        ledger = run()
        for day in (2, 3, 4, 5):
            self.assertEqual(ledger.fees_for_day(A1, day), 0)
        self.assertEqual(ledger.balance(A1, 2), 25000)
        self.assertEqual(len(kinds(ledger, "FEE")), 3)           # still on the ledger
        self.assertEqual(len(kinds(ledger, "FEE_REVERSAL")), 3)  # undone by new entries
        self.assertEqual(ledger.auth_state("Auth-B").state, DECLINED)  # not re-approved

    def test_c7_instalments_are_3333_3333_3334(self):
        parts = [e.amount for e in ledger_entries(run(), A2, "CREDIT")]
        self.assertEqual(parts, [3333, 3333, 3334])
        self.assertEqual(sum(parts), 10000)
        self.assertNotEqual(3 * 3334, 10000)

    def test_c8_daily_accruals_sum_exactly_to_capitalised(self):
        ledger = run()
        for account, expected in ((A1, 79), (A2, 8)):
            per_day = [ledger.accrual_for_day(account, d) for d in range(1, 7)]
            capitalised = [e.amount for e in ledger_entries(ledger, account, "INTEREST")]
            self.assertEqual(capitalised, [expected])
            self.assertEqual(sum(per_day), expected)


def ledger_entries(ledger, account, kind):
    return [e for e in ledger.entries if e.account == account and e.kind == kind]


class Invariants(unittest.TestCase):
    def test_final_closing_balances(self):
        ledger = run()
        self.assertEqual(ledger.reports[-1]["accounts"][A1]["closing"], 28579)
        self.assertEqual(ledger.reports[-1]["accounts"][A2]["closing"], 10008)
        self.assertEqual([ledger.accrual_for_day(A1, d) for d in range(1, 7)],
                         [10, 10, 26, 11, 11, 11])

    def test_append_only_every_earlier_state_is_a_prefix(self):
        ledger = Ledger(ACCOUNTS)
        seen = []
        for ev in STREAM:
            ledger.apply(ev)
            self.assertEqual(ledger.entries[:len(seen)], seen)
            seen = list(ledger.entries)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ledger.entries[0].amount = 0

    def test_restatement_is_idempotent(self):
        ledger = run()
        count = len(ledger.entries)
        ledger.day = 6                           # re-run the Day 6 restatement by hand
        for day in range(1, 7):
            ledger._restate_fee(A1, "AED", day, "TEST")
        self.assertEqual(len(ledger.entries), count)

    def test_at_most_one_net_fee_per_day(self):
        ledger = replay_until("E8")
        ledger.close_day()
        for day in range(1, 6):
            self.assertIn(ledger.fees_for_day(A1, day), (0, 2500))

    def test_reversing_twice_is_refused(self):
        ledger = run()
        before = len(ledger.entries)
        ledger.day = 6
        ledger.apply(Event("E9b", 6, "REVERSAL", A1, value_day=2, target="E7"))
        self.assertEqual(len(ledger.entries), before)
        self.assertTrue(any(n.source == "E9b" and n.level == "ERROR" for n in ledger.notices))

    def test_duplicate_event_is_ignored(self):
        ledger = replay_until("E2")
        ledger.apply(STREAM[1])
        self.assertEqual(ledger.balance(A1, 1), 25000)

    def test_split_always_sums(self):
        for total in range(0, 2000):
            for parts in (1, 2, 3, 7):
                self.assertEqual(sum(split_evenly(total, parts)), total)


if __name__ == "__main__":
    unittest.main()
