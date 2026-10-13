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
    def test_headline_figures(self):
        ledger = run()
        self.assertEqual(ledger.reports[4]["accounts"][A1]["closing"], -41000)   # Day 5 close
        self.assertEqual(ledger.reports[4]["accounts"][A2]["closing"], 0)        # E10 not yet arrived
        self.assertEqual(replay_until("E8").available(A1), -33500)            # Auth-B saw this
        self.assertIn("-425.00 AED", ledger.auth_state("Auth-B").reason)      # available after its hold

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

    def test_accrual_restatement_ignores_the_capitalised_credit(self):
        # A positive account: re-running the Day 6 accrual must not earn interest on the interest.
        ledger = Ledger({A1: "AED"})
        ledger.apply(Event("C", 1, "CREDIT", A1, 1000000, value_day=1))
        for _ in range(6):
            ledger.close_day()
        ledger.day = 6
        for day in range(1, 7):
            ledger._restate_accrual(A1, day)
        accrued = sum(a.amount for a in ledger.accruals)
        self.assertEqual(accrued, sum(e.amount for e in kinds(ledger, "INTEREST")))
        self.assertEqual(accrued, 2400)                      # 6 days x 4.00

    def test_events_after_the_window_closes_are_refused(self):
        ledger = run()
        before = len(ledger.entries)
        ledger.apply(Event("LATE", 6, "DEBIT", A1, 100000, value_day=3))
        self.assertEqual(len(ledger.entries), before)
        self.assertTrue(errors(ledger, "LATE"))

    def test_invalid_events_are_errors_and_keep_their_id(self):
        ledger = replay_until("E2")
        for bad in (Event("X", 1, "DEBIT", A1, 100, value_day=2),       # value date tomorrow
                    Event("X", 1, "CREDIT", A1, 100, value_day=0),      # before the window
                    Event("X", 1, "SETTLEMENT", A1, 100, value_day=2, auth_id="Auth-Q"),
                    Event("X", 1, "REVERSAL", A1, value_day=2, target="E2"),
                    Event("X", 1, "TRANSFER", A1, 100, value_day=1),    # unknown type
                    Event("X", 1, "DEBIT", A1, -100, value_day=1),      # negative amount
                    Event("X", 1, "REVERSAL", A1, target="E2")):        # no value date
            ledger.apply(bad)
        self.assertEqual(len(errors(ledger, "X")), 7)
        ledger.apply(Event("X", 1, "DEBIT", A1, 100, value_day=1))     # the corrected retry
        self.assertEqual(ledger.balance(A1, 1), 24900)

    def test_reversal_must_name_the_targets_account_and_keeps_its_id(self):
        ledger = replay_until("E8")
        ledger.apply(Event("R", 5, "REVERSAL", A2, value_day=2, target="E7"))
        self.assertEqual(kinds(ledger, "REVERSAL", A2), [])
        self.assertTrue(errors(ledger, "R"))
        ledger.apply(Event("R", 5, "REVERSAL", A1, value_day=2, target="E7"))   # corrected retry, same id
        self.assertEqual([e.amount for e in kinds(ledger, "REVERSAL")], [62000])

    def test_settlement_reversal_credits_money_but_keeps_the_decision(self):
        ledger = replay_until("E5")
        ledger.apply(Event("R5", 4, "REVERSAL", A1, value_day=4, target="E5"))
        self.assertEqual([e.amount for e in kinds(ledger, "REVERSAL")], [18500])
        self.assertEqual(ledger.auth_state("Auth-A").state, SETTLED)

    def test_a_reversal_is_full_and_cannot_target_a_reversal(self):
        ledger = replay_until("E8")
        ledger.apply(Event("RP", 5, "REVERSAL", A1, 10000, value_day=2, target="E7"))   # partial: refused
        ledger.apply(Event("E9", 6, "REVERSAL", A1, value_day=2, target="E7"))
        ledger.apply(Event("RR", 6, "REVERSAL", A1, value_day=2, target="E9"))
        self.assertIn("always full", errors(ledger, "RP")[0])
        self.assertIn("itself a reversal", errors(ledger, "RR")[0])
        self.assertEqual([e.amount for e in kinds(ledger, "REVERSAL")], [62000])

    def test_booked_day_outside_the_window_is_refused(self):
        ledger = Ledger(ACCOUNTS)
        ledger.apply(Event("B0", 0, "CREDIT", A1, 100, value_day=1))
        ledger.apply(Event("B7", 7, "CREDIT", A1, 100, value_day=1))
        self.assertTrue(errors(ledger, "B0") and errors(ledger, "B7"))
        self.assertEqual((ledger.entries, ledger.day), ([], 1))   # nothing posted, no day closed

    def test_parts_cannot_exceed_the_amount(self):
        ledger = replay_until("E2")
        ledger.apply(Event("P5", 1, "CREDIT", A1, 2, value_day=1, parts=5))          # 0.02 in five parts
        ledger.apply(Event("PH", 1, "CREDIT", A1, 100, value_day=1, parts=2 ** 62))  # would exhaust memory
        self.assertTrue(errors(ledger, "P5") and errors(ledger, "PH"))
        ledger.apply(Event("P5", 1, "CREDIT", A1, 5, value_day=1, parts=5))          # corrected: 0.01 each
        self.assertEqual([e.amount for e in kinds(ledger, "CREDIT")][-5:], [1, 1, 1, 1, 1])

    def test_a_finished_authorization_id_cannot_be_reused(self):
        ledger = replay_until("E8")                                  # Auth-A SETTLED, Auth-B DECLINED
        for i, auth in enumerate(("Auth-A", "Auth-B")):
            ledger.apply(Event(f"D{i}", 5, "AUTHORIZATION", A2, 1, auth_id=auth))   # funds are irrelevant
        self.assertTrue(errors(ledger, "D0") and errors(ledger, "D1"))
        self.assertEqual((ledger.auth_state("Auth-A").state, ledger.auth_state("Auth-B").state), (SETTLED, DECLINED))

    def test_back_valued_note_is_for_money_events_only(self):
        ledger = replay_until("E2")
        ledger.apply(Event("C3", 3, "CREDIT", A1, 100, value_day=3))                  # now on Day 3
        ledger.apply(Event("LA", 2, "AUTHORIZATION", A1, 100, value_day=2, auth_id="Auth-L"))
        ledger.apply(Event("LD", 2, "DEBIT", A1, 100, value_day=2))
        levels = lambda src: sorted(n.level for n in ledger.notices if n.source == src)
        self.assertEqual(levels("LA"), ["WARNING"])                 # late, but a hold has no value date
        self.assertEqual(levels("LD"), ["INFO", "WARNING"])         # late and back-valued

    def test_authorization_without_an_id_is_refused(self):
        ledger = replay_until("E2")
        ledger.apply(Event("NA", 1, "AUTHORIZATION", A1, 100))
        self.assertTrue(errors(ledger, "NA"))
        self.assertIsNone(ledger.auth_state(None))

    def test_a_content_refusal_still_advances_the_day(self):
        ledger = replay_until("E2")                                  # still Day 1
        ledger.apply(Event("BAD", 4, "TRANSFER", A1, 100, value_day=4))
        self.assertTrue(errors(ledger, "BAD"))
        self.assertEqual(ledger.day, 4)                              # Days 1-3 were closed on its arrival

    def test_duplicate_authorization_keeps_its_event_id(self):
        ledger = replay_until("E3")
        ledger.apply(Event("A2", 2, "AUTHORIZATION", A1, 1000, auth_id="Auth-A"))   # Auth-A exists
        self.assertTrue(errors(ledger, "A2"))
        self.assertNotIn("A2", ledger.received)
        ledger.apply(Event("A2", 2, "AUTHORIZATION", A1, 1000, auth_id="Auth-C"))   # corrected retry
        self.assertEqual(ledger.auth_state("Auth-C").state, APPROVED)

    def test_amount_and_parts_boundaries(self):
        ledger = replay_until("E2")
        ledger.apply(Event("Z0", 1, "DEBIT", A1, 0, value_day=1))
        ledger.apply(Event("P0", 1, "CREDIT", A1, 100, value_day=1, parts=0))
        ledger.apply(Event("PN", 1, "CREDIT", A1, 100, value_day=1, parts=-1))
        ledger.apply(Event("AV", 1, "AUTHORIZATION", A1, 0, auth_id="Auth-V"))  # account verification
        ledger.apply(Event("AN", 1, "AUTHORIZATION", A1, -50000, auth_id="Auth-N"))  # would raise available
        self.assertEqual([bool(errors(ledger, x)) for x in ("Z0", "P0", "PN", "AV", "AN")], [True, True, True, False, True])
        self.assertIsNone(ledger.auth_state("Auth-N"))
        self.assertEqual(ledger.balance(A1, 1), 25000)
        self.assertEqual(ledger.auth_state("Auth-V").state, APPROVED)

    def test_reversal_undoes_every_instalment(self):
        ledger = replay_until("E10")                 # Day 6 still open
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
