"""Replay the event stream and print, per day: closing ledger balance, fee
assessments, authorization states and errors.

    python3 replay.py
"""
from ledger.core import LAST_DAY, Ledger
from ledger.money import fmt
from ledger.stream import ACCOUNTS, STREAM


def run() -> Ledger:
    ledger = Ledger(ACCOUNTS)
    for event in STREAM:
        ledger.apply(event)
    while ledger.day <= LAST_DAY:     # close whatever days the stream did not reach
        ledger.close_day()
    return ledger


def print_report(r: dict) -> None:
    print(f"\n=== Day {r['day']} close " + "=" * 50)
    for account, a in r["accounts"].items():
        ccy = a["ccy"]
        print(f"{account}  closing ledger {fmt(a['closing'], ccy):>16}"
              f"   available {fmt(a['available'], ccy):>16}   holds {fmt(a['holds'], ccy)}")
        for day, was, now in a["restated"]:
            print(f"    restated  Day {day} closing {fmt(was, ccy)} -> {fmt(now, ccy)}")
        for e in a["fees"]:
            label = "fee assessed" if e.kind == "FEE" else "fee reversed"
            print(f"    {label}  {fmt(abs(e.amount), ccy)} value Day {e.value_day}")
        for x in a["accruals"]:
            print(f"    accrual   Day {x.day} {'+' if x.amount > 0 else ''}{fmt(x.amount, ccy)}")
        for e in a["interest"]:
            print(f"    interest capitalised {fmt(e.amount, ccy)} value Day {e.value_day}")
    print("  authorizations:")
    for t in r["auths"]:
        print(f"    {t.auth_id:7} {t.state:9} ({t.source}: {t.reason})")
    if not r["auths"]:
        print("    none")
    print("  errors and exceptions:")
    shown = [n for n in r["notices"] if n.level != "INFO"]
    for n in shown:
        print(f"    {n.level:9} {n.source}: {n.message}")
    if not shown:
        print("    none")
    for n in r["notices"]:
        if n.level == "INFO":
            print(f"  note: {n.source} {n.message}")


if __name__ == "__main__":
    for report in run().reports:
        print_report(report)
