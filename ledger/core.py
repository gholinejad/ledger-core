"""In-memory, append-only account ledger.

Three append-only logs, none of which is ever edited:
  entries   - money movements on the ledger (credits, debits, fees, interest ...)
  accruals  - interest accrual memos (not ledger entries until capitalised)
  auth_log  - authorization state transitions (holds are not ledger entries)

Back-valued events are never handled by editing the past. Every end-of-day
close re-evaluates every day of the window as it is now known, and posts the
*difference* as a new compensating record (FEE_REVERSAL, accrual delta).
"""
from dataclasses import dataclass
from decimal import Decimal

from .money import apply_rate, fmt, split_evenly

FIRST_DAY, LAST_DAY = 1, 6
OVERDRAFT_FEE = {"AED": 2500}        # AED 25.00 in fils; no fee is defined for BHD
DAILY_RATE = Decimal("0.0004")       # 0.04 % per day

FEE_KINDS = ("FEE", "FEE_REVERSAL")
REVERSIBLE = ("CREDIT", "DEBIT", "SETTLEMENT", "FORCE_POST")   # money an event moved; never fees or interest
EVENT_TYPES = ("CREDIT", "DEBIT", "AUTHORIZATION", "SETTLEMENT", "REVERSAL")
APPROVED, DECLINED, SETTLED = "APPROVED", "DECLINED", "SETTLED"


@dataclass(frozen=True)
class Event:
    id: str
    booked_day: int
    type: str                  # CREDIT DEBIT AUTHORIZATION SETTLEMENT REVERSAL
    account: str
    amount: int = 0            # minor units, always positive in the event
    value_day: int | None = None
    auth_id: str | None = None
    target: str | None = None  # event id a REVERSAL undoes
    parts: int = 1             # CREDIT posted as this many instalments


@dataclass(frozen=True)
class Entry:
    seq: int
    account: str
    kind: str          # CREDIT DEBIT SETTLEMENT FORCE_POST REVERSAL FEE FEE_REVERSAL INTEREST
    amount: int        # signed minor units: + credit, - debit
    value_day: int
    booked_day: int    # the day the ledger actually recorded it
    source: str        # event id, or EOD<n> for entries the close generated
    reverses: str | None = None   # for REVERSAL: the event id it undoes
    event: str | None = None      # the event that caused it (shared by all instalments); None for EOD entries


@dataclass(frozen=True)
class Accrual:
    account: str
    day: int           # the day the interest belongs to
    amount: int        # delta; sum per day = that day's rounded accrual
    booked_day: int


@dataclass(frozen=True)
class AuthTransition:
    auth_id: str
    account: str
    state: str
    amount: int
    booked_day: int
    source: str
    reason: str


@dataclass(frozen=True)
class Notice:
    booked_day: int
    source: str
    level: str         # ERROR (rejected) | EXCEPTION (posted, needs ops review) | WARNING | INFO
    message: str


class LedgerError(Exception):
    """Misuse of the ledger API itself (not a business rejection)."""


class Ledger:
    def __init__(self, accounts: dict[str, str]):
        self.ccy = dict(accounts)             # account -> currency
        self.day = FIRST_DAY                  # current business (booking) day
        self.entries: list[Entry] = []
        self.accruals: list[Accrual] = []
        self.auth_log: list[AuthTransition] = []
        self.notices: list[Notice] = []
        self.received: list[str] = []         # event ids, in arrival order
        self.reported: dict[tuple[str, int], int] = {}  # (account, day) -> closing as last printed
        self.reports: list[dict] = []

    # ---------------------------------------------------------------- queries
    def balance(self, account: str, as_of_day: int, exclude_fee_day: int | None = None,
                before_capitalisation: bool = False) -> int:
        """Ledger balance = all entries with value_day <= as_of_day.

        exclude_fee_day leaves out that one day's own fee, so a fee can never
        justify itself when the overdraft test is re-run.
        before_capitalisation leaves out the end-of-window INTEREST credit: the
        fee test and the accrual both read the day as it stood before
        capitalisation, otherwise the capitalised amount would feed back into
        the Day 6 accrual it is the sum of.
        """
        return sum(
            e.amount for e in self.entries
            if e.account == account and e.value_day <= as_of_day
            and not (e.kind in FEE_KINDS and e.value_day == exclude_fee_day)
            and not (before_capitalisation and e.kind == "INTEREST")
        )

    def auth_state(self, auth_id: str) -> AuthTransition | None:
        for t in reversed(self.auth_log):
            if t.auth_id == auth_id:
                return t
        return None

    def active_holds(self, account: str) -> int:
        latest: dict[str, AuthTransition] = {}
        for t in self.auth_log:
            if t.account == account:
                latest[t.auth_id] = t
        return sum(t.amount for t in latest.values() if t.state == APPROVED)

    def available(self, account: str) -> int:
        return self.balance(account, self.day) - self.active_holds(account)

    def fees_for_day(self, account: str, day: int) -> int:
        """Net fee charged for `day`, as a positive number."""
        return -sum(e.amount for e in self.entries
                    if e.account == account and e.kind in FEE_KINDS and e.value_day == day)

    def accrual_for_day(self, account: str, day: int) -> int:
        return sum(a.amount for a in self.accruals if a.account == account and a.day == day)

    # ---------------------------------------------------------------- writes
    def _post(self, account: str, kind: str, amount: int, value_day: int, source: str,
              reverses: str | None = None, event: str | None = None) -> Entry:
        if not FIRST_DAY <= value_day <= self.day:
            raise LedgerError(f"{source}: value day {value_day} outside Day {FIRST_DAY}..{self.day}")
        entry = Entry(len(self.entries) + 1, account, kind, amount, value_day, self.day, source, reverses, event)
        self.entries.append(entry)
        return entry

    def _notice(self, source: str, level: str, message: str) -> None:
        self.notices.append(Notice(self.day, source, level, message))

    def _auth(self, auth_id, account, state, amount, source, reason) -> None:
        self.auth_log.append(AuthTransition(auth_id, account, state, amount, self.day, source, reason))

    # ---------------------------------------------------------------- events
    def apply(self, ev: Event) -> None:
        if ev.id in self.received:
            self._notice(ev.id, "ERROR", "duplicate event id, ignored")
            return
        if ev.account not in self.ccy:
            self._notice(ev.id, "ERROR", f"unknown account {ev.account}, ignored")
            return
        if ev.booked_day > LAST_DAY:
            self._notice(ev.id, "ERROR", f"booked Day {ev.booked_day} is outside the window, ignored")
            return
        if self.day > LAST_DAY:
            self._notice(ev.id, "ERROR", "the window is closed (Day 6 is capitalised), not posted")
            return
        while self.day < ev.booked_day:       # stream moved on: close the days in between
            self.close_day()
        problem = self._invalid(ev)
        if problem:                           # refused before its id is consumed, so a fixed retry can use it
            self._notice(ev.id, "ERROR", f"{problem}, not posted")
            return
        self.received.append(ev.id)
        if ev.booked_day < self.day:
            self._notice(ev.id, "WARNING",
                         f"late arrival: booked Day {ev.booked_day}, processed on Day {self.day}")
        if ev.value_day is not None and ev.value_day < self.day:
            self._notice(ev.id, "INFO", f"back-valued to Day {ev.value_day}")

        handler = {
            "CREDIT": self._credit, "DEBIT": self._debit, "AUTHORIZATION": self._authorize,
            "SETTLEMENT": self._settle, "REVERSAL": self._reverse,
        }[ev.type]
        handler(ev)

    def _invalid(self, ev: Event) -> str | None:
        """Why this event cannot be posted on the current day, or None."""
        if ev.type not in EVENT_TYPES:
            return f"unknown event type {ev.type}"
        if ev.type != "REVERSAL" and ev.amount <= 0:
            return "amount must be positive"
        if ev.type == "CREDIT" and ev.parts < 1:
            return "parts must be at least 1"
        if ev.type == "AUTHORIZATION":
            return None                       # a hold has no value date on the ledger
        if ev.value_day is None:
            return "value date missing"
        if not FIRST_DAY <= ev.value_day <= self.day:
            return f"value Day {ev.value_day} is outside Day {FIRST_DAY}..{self.day} (future value dates are not supported)"
        return None

    def _credit(self, ev: Event) -> None:
        for i, part in enumerate(split_evenly(ev.amount, ev.parts), start=1):
            source = ev.id if ev.parts == 1 else f"{ev.id}#{i}"
            self._post(ev.account, "CREDIT", part, ev.value_day, source, event=ev.id)

    def _debit(self, ev: Event) -> None:
        self._post(ev.account, "DEBIT", -ev.amount, ev.value_day, ev.id, event=ev.id)

    def _authorize(self, ev: Event) -> None:
        if self.auth_state(ev.auth_id) is not None:
            self._notice(ev.id, "ERROR", f"{ev.auth_id} already exists, ignored")
            return
        after = self.available(ev.account) - ev.amount
        ccy = self.ccy[ev.account]
        if after >= 0:
            self._auth(ev.auth_id, ev.account, APPROVED, ev.amount, ev.id,
                       f"available after hold {fmt(after, ccy)}")
        else:
            self._auth(ev.auth_id, ev.account, DECLINED, ev.amount, ev.id,
                       f"available after hold would be {fmt(after, ccy)}")

    def _settle(self, ev: Event) -> None:
        auth = self.auth_state(ev.auth_id)
        ccy = self.ccy[ev.account]
        if auth is not None and auth.state == APPROVED and auth.account == ev.account:
            self._post(ev.account, "SETTLEMENT", -ev.amount, ev.value_day, ev.id, event=ev.id)
            released = auth.amount - ev.amount
            self._auth(ev.auth_id, ev.account, SETTLED, 0, ev.id,
                       f"settled {fmt(ev.amount, ccy)}; hold {fmt(auth.amount, ccy)} released"
                       + (f" ({fmt(released, ccy)} never charged)" if released > 0 else ""))
            if released < 0:
                self._notice(ev.id, "EXCEPTION",
                             f"{ev.auth_id} settled {fmt(-released, ccy)} above its hold")
            return
        # No approved authorization to match. The scheme has already paid the
        # merchant, so refusing the debit would not stop the money leaving the
        # bank. Post it, and raise it for dispute / chargeback review.
        why = "unknown authorization" if auth is None else f"authorization is {auth.state}"
        self._post(ev.account, "FORCE_POST", -ev.amount, ev.value_day, ev.id, event=ev.id)
        self._notice(ev.id, "EXCEPTION",
                     f"{ev.auth_id}: {why}; {fmt(ev.amount, ccy)} force-posted, "
                     f"queued for chargeback review")

    def _reverse(self, ev: Event) -> None:
        """Undo the money an earlier event moved: every entry it caused, instalments included.

        A reversal undoes money, never a decision: authorization states are untouched.
        Reversing a FORCE_POST is the chargeback credit when a dispute is won.
        """
        if ev.target not in self.received:
            self._notice(ev.id, "ERROR", f"nothing to reverse: no event {ev.target}")
            return
        targets = [e for e in self.entries if e.event == ev.target and e.kind in REVERSIBLE]
        if not targets:
            self._notice(ev.id, "ERROR", f"nothing to reverse: {ev.target} moved no money (a hold or a refusal)")
            return
        if any(t.account != ev.account for t in targets):
            self._notice(ev.id, "ERROR", f"{ev.target} belongs to {targets[0].account}, not {ev.account}")
            return
        if any(e.kind == "REVERSAL" and e.reverses == ev.target for e in self.entries):
            self._notice(ev.id, "ERROR", f"{ev.target} is already reversed")
            return
        for t in targets:
            self._post(ev.account, "REVERSAL", -t.amount, ev.value_day, ev.id, reverses=ev.target, event=ev.id)

    # ---------------------------------------------------------------- end of day
    def close_day(self) -> dict:
        """Close the current business day, then advance to the next one."""
        if self.day > LAST_DAY:
            raise LedgerError("window already closed")
        d = self.day
        first_new_entry, first_new_accrual = len(self.entries), len(self.accruals)
        source = f"EOD{d}"

        for account, ccy in self.ccy.items():
            for day in range(FIRST_DAY, d + 1):   # oldest first: a fee on day N moves day N+1
                self._restate_fee(account, ccy, day, source)
                self._restate_accrual(account, day)
        if d == LAST_DAY:
            for account in self.ccy:
                total = sum(a.amount for a in self.accruals if a.account == account)
                if total:
                    self._post(account, "INTEREST", total, LAST_DAY, source)

        report = self._report(d, first_new_entry, first_new_accrual)
        self.reports.append(report)
        self.day += 1
        return report

    def _restate_fee(self, account: str, ccy: str, day: int, source: str) -> None:
        before_own_fee = self.balance(account, day, exclude_fee_day=day, before_capitalisation=True)
        owed = 0
        if before_own_fee < 0:
            if ccy not in OVERDRAFT_FEE:
                self._notice(source, "ERROR", f"{account} overdrawn on Day {day} but no {ccy} fee is defined")
                return
            owed = OVERDRAFT_FEE[ccy]
        delta = owed - self.fees_for_day(account, day)
        if delta > 0:
            self._post(account, "FEE", -delta, day, source)
        elif delta < 0:
            self._post(account, "FEE_REVERSAL", -delta, day, source)

    def _restate_accrual(self, account: str, day: int) -> None:
        closing = self.balance(account, day, before_capitalisation=True)
        owed = apply_rate(closing, DAILY_RATE) if closing > 0 else 0
        delta = owed - self.accrual_for_day(account, day)
        if delta:
            self.accruals.append(Accrual(account, day, delta, self.day))

    def _report(self, d: int, first_new_entry: int, first_new_accrual: int) -> dict:
        accounts = {}
        for account, ccy in self.ccy.items():
            restated = []
            for day in range(FIRST_DAY, d):
                now = self.balance(account, day)
                if now != self.reported[(account, day)]:
                    restated.append((day, self.reported[(account, day)], now))
                    self.reported[(account, day)] = now
            closing = self.balance(account, d)   # Day 6 includes the capitalised interest
            self.reported[(account, d)] = closing
            accounts[account] = {
                "ccy": ccy,
                "closing": closing,
                "available": closing - self.active_holds(account),
                "holds": self.active_holds(account),
                "fees": [e for e in self.entries[first_new_entry:]
                         if e.account == account and e.kind in FEE_KINDS],
                "interest": [e for e in self.entries[first_new_entry:]
                             if e.account == account and e.kind == "INTEREST"],
                "accruals": [a for a in self.accruals[first_new_accrual:] if a.account == account],
                "restated": restated,
            }
        return {
            "day": d,
            "accounts": accounts,
            "auths": [self.auth_state(a) for a in dict.fromkeys(t.auth_id for t in self.auth_log)],
            "notices": [n for n in self.notices if n.booked_day == d],
        }
