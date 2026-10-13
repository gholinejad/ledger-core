"""THE ONE DELIBERATELY FAILING TEST.

It asserts something a bank customer would reasonably expect, and my design
does not deliver it. It is kept failing on purpose; see REJECTED.md.

    python3 -m unittest tests.test_known_failure -v
"""
import unittest

from replay import run


class KnownFailure(unittest.TestCase):
    def test_day5_statement_includes_everything_booked_on_day5(self):
        ledger = run()
        day5 = ledger.reports[4]
        assert day5["day"] == 5

        # E10 is booked on Day 5 with value Day 5, so a Day 5 statement for
        # ACC-002 "should" show BHD 10.000.
        #
        # WHAT IT REVEALS: my ledger's notion of "today" is the position in
        # the stream, not the event's booking date. E10 reaches the ledger
        # after E9 (a Day 6 event), when Day 5 is already closed and printed
        # as 0.000. The ledger does not lose the money: on Day 6 it posts E10
        # back-valued, restates Day 5 to 10.000 and accrues Day 5 interest.
        # But the Day 5 statement went out wrong, and a printed statement
        # cannot be recalled, only corrected.
        #
        # This is a design choice, not a bug I can fix in the core: holding
        # Day 5 open until "everything for Day 5 has arrived" needs a cut-off
        # (watermark) that the brief does not define. In production that is
        # an operational control (late-arrival cut-off + correction notice),
        # described in the architecture document.
        self.assertEqual(day5["accounts"]["ACC-002"]["closing"], 10000)  # actual: 0


if __name__ == "__main__":
    unittest.main()
