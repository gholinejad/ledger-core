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


def errors(ledger, source):
    return [n.message for n in ledger.notices if n.source == source and n.level == "ERROR"]


class EdgeCases(unittest.TestCase):
    """Cases outside the brief's stream, found by the pre-submission review."""

    def test_restatement_is_idempotent_after_capitalisation(self):
        # Day 6 is negative only before the interest credit lands: the fee test and
        # the accrual must read the same pre-capitalisation balance every time.
        ledger = Ledger({A1: "AED"})
        ledger.apply(Event("C", 1, "CREDIT", A1, 100000, value_day=1))
        ledger.apply(Event("D", 6, "DEBIT", A1, 100050, value_day=6))
        ledger.close_day()
        entries, accruals = len(ledger.entries), len(ledger.accruals)
        ledger.day = 6                           # re-run the Day 6 restatement by hand
        for day in range(1, 7):
            ledger._restate_fee(A1, "AED", day, "TEST")
            ledger._restate_accrual(A1, day)
        self.assertEqual((len(ledger.entries), len(ledger.accruals)), (entries, accruals))
        self.assertEqual(ledger.fees_for_day(A1, 6), 2500)   # -0.50 before capitalisation

    def test_events_after_the_window_closes_are_refused(self):
        ledger = run()
        before = len(ledger.entries)
        ledger.apply(Event("LATE", 6, "DEBIT", A1, 100000, value_day=3))
        self.assertEqual(len(ledger.entries), before)
        self.assertTrue(errors(ledger, "LATE"))

    def test_invalid_events_are_errors_and_keep_their_id(self):
        ledger = replay_until("E2")
        for bad in (Event("X", 1, "DEBIT", A1, 100, value_day=3),       # future value date
                    Event("X", 1, "TRANSFER", A1, 100, value_day=1),    # unknown type
                    Event("X", 1, "DEBIT", A1, -100, value_day=1),      # negative amount
                    Event("X", 1, "REVERSAL", A1, target="E2")):        # no value date
            ledger.apply(bad)
        self.assertEqual(len(errors(ledger, "X")), 4)
        ledger.apply(Event("X", 1, "DEBIT", A1, 100, value_day=1))     # the corrected retry
        self.assertEqual(ledger.balance(A1, 1), 24900)

    def test_reversal_must_name_the_targets_account(self):
        ledger = replay_until("E8")
        ledger.apply(Event("R", 5, "REVERSAL", A2, value_day=2, target="E7"))
        self.assertEqual(kinds(ledger, "REVERSAL", A2), [])
        self.assertTrue(errors(ledger, "R"))
        ledger.apply(Event("E9", 6, "REVERSAL", A1, value_day=2, target="E7"))
        self.assertEqual([e.amount for e in kinds(ledger, "REVERSAL")], [62000])   # the real one still works

    def test_reversal_undoes_every_instalment(self):
        ledger = run()
        ledger.day = 6
        ledger.apply(Event("R10", 6, "REVERSAL", A2, value_day=5, target="E10"))
        self.assertEqual([e.amount for e in kinds(ledger, "REVERSAL", A2)], [-3333, -3333, -3334])
        self.assertEqual(ledger.balance(A2, 5), 0)

    def test_chargeback_credit_reverses_a_force_post(self):
        ledger = replay_until("E6")
        ledger.apply(Event("CB", 4, "REVERSAL", A1, value_day=4, target="E6"))
        self.assertEqual([e.amount for e in kinds(ledger, "REVERSAL")], [18000])
        self.assertEqual(ledger.balance(A1, 4), 46500)       # as if Auth-Z never settled

    def test_reversing_a_hold_or_unknown_event_says_why(self):
        ledger = replay_until("E3")
        ledger.apply(Event("R3", 2, "REVERSAL", A1, value_day=2, target="E3"))
        ledger.apply(Event("R99", 2, "REVERSAL", A1, value_day=2, target="E99"))
        self.assertIn("moved no money", errors(ledger, "R3")[0])
        self.assertIn("no event E99", errors(ledger, "R99")[0])


if __name__ == "__main__":
    unittest.main()
