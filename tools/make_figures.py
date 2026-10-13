"""Draw the figures used by the documents into docs/img/*.svg.

    python3 tools/make_figures.py

Standard library only. The architecture figures are diagrams of the design; none of them restates the
event stream. The README figures replay the ledger, so every number on them comes from the code.
"""
import os
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "img")

INK, INK2, MUTED, RULE, SOFT = "#14213d", "#3b4a66", "#6b7890", "#d5dbe6", "#f4f6fa"
ACC, ACCS, RED, REDS, OK, OKS = "#1f5fbf", "#e8f0fb", "#b3261e", "#fbe9e7", "#2f7d4f", "#e7f3ec"
WARN, WARNS, OLD = "#b26a00", "#fdf3e2", "#8a94a6"


def t(x, y, s, size=12, fill=INK, weight=400, anchor="start"):
    return (f"<text x='{x:.1f}' y='{y:.1f}' font-size='{size}' fill='{fill}' font-weight='{weight}' "
            f"text-anchor='{anchor}'>{escape(s, quote=False)}</text>")


def rect(x, y, w, h, fill, stroke="none", sw=0, rx=6, dash=""):
    d = f" stroke-dasharray='{dash}'" if dash else ""
    return (f"<rect x='{x:.1f}' y='{y:.1f}' width='{w:.1f}' height='{h:.1f}' rx='{rx}' fill='{fill}' "
            f"stroke='{stroke}' stroke-width='{sw}'{d}/>")


def line(x1, y1, x2, y2, c=INK2, w=1.5, dash="", arrow=False):
    d = f" stroke-dasharray='{dash}'" if dash else ""
    m = f" marker-end='url(#a{c[1:]})'" if arrow else ""
    return f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='{c}' stroke-width='{w}'{d}{m}/>"


def curve(d, c, w=1.6, dash=""):
    ds = f" stroke-dasharray='{dash}'" if dash else ""
    return f"<path d='{d}' stroke='{c}' stroke-width='{w}' fill='none'{ds} marker-end='url(#a{c[1:]})'/>"


def svg(w, h, body, label):
    marks = "".join(f"<marker id='a{c[1:]}' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' "
                    f"orient='auto-start-reverse'><path d='M0 0L10 5L0 10z' fill='{c}'/></marker>"
                    for c in (INK2, ACC, RED, OK, WARN, OLD))
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' role='img' aria-label='{label}' "
            f"font-family='Inter, Helvetica, Arial, sans-serif'><defs>{marks}</defs>"
            f"<rect width='{w}' height='{h}' fill='#ffffff'/>{body}</svg>\n")


def close_cost():
    """What one end-of-day close computes today, and after the snapshot + dirty-from change."""
    W, H = 760, 214
    days, accts, cw, ch = 12, 5, 24, 20
    b = ""

    def grid(x0, title, sub, shade):
        o = t(x0 - 46, 18, title, 13, INK, 700) + t(x0 - 46, 35, sub, 11, MUTED)
        for a in range(accts):
            o += t(x0 - 8, 62 + a * ch + 14, f"acct {a + 1}", 10, MUTED, 400, "end")
            for d in range(days):
                on = shade(a, d)
                o += rect(x0 + d * cw, 62 + a * ch, cw - 3, ch - 3, ACC if on else SOFT, ACC if on else RULE, 0.8, 2)
        o += t(x0, 62 + accts * ch + 16, "day 1", 10, MUTED)
        o += t(x0 + (days - 1) * cw + cw - 3, 62 + accts * ch + 16, f"today (day {days})", 10, MUTED, 400, "end")
        return o
    b += grid(56, "Today: every close re-tests every day of every account",
              "cost ≈ accounts × days × entries (balance() scans the whole log)", lambda a, d: True)
    b += grid(446, "After: daily snapshots + a dirty-from mark per account",
              "cost ≈ accounts + dirty account-days since each back-value",
              lambda a, d: d == days - 1 or (a == 1 and d >= 3) or (a == 3 and d >= 9))
    b += t(446 + 3 * cw, 56, "▼ back-value lands on day 4", 10.5, RED, 700)
    return svg(W, H, b, "Close cost before and after the snapshot change")


def backvalue_gate():
    """The one control before go-live, in the order its checks run."""
    W, H = 850, 176
    b = ""
    y0, h = 40, 56
    boxes = [(8, 120, "entry arrives", "", SOFT, INK2),
             (150, 136, "value date", "before today?", ACCS, ACC),
             (310, 136, "crosses a", "sealed period?", REDS, RED),
             (470, 120, "system", "compensation?", SOFT, INK2),
             (614, 138, "reason code", "+ second approver", WARNS, WARN)]
    for x, w, n, s2, cs, c in boxes:
        b += rect(x, y0, w, h, cs, c, 1.6, 8) + t(x + 10, y0 + 23, n, 12, c, 700)
        if s2:
            b += t(x + 10, y0 + 41, s2, 12, c, 700)
    for x1, x2, lab in ((128, 148, ""), (286, 308, "yes"), (446, 468, "no"), (590, 612, "no")):
        b += line(x1, y0 + 28, x2, y0 + 28, INK2, 1.6, arrow=True)
        if lab:
            b += t((x1 + x2) / 2, y0 + 20, lab, 10, MUTED, 600, "middle")
    b += line(218, y0 + h, 218, 128, OK, 1.4, arrow=True) + t(226, 122, "no: post normally", 10.5, OK, 600)
    b += line(378, y0 + h, 378, 150, RED, 1.4, arrow=True) + t(386, 146, "yes: refuse; post today with a reference", 10.5, RED, 600)
    b += line(530, y0 + h, 530, 128, OK, 1.4, arrow=True) + t(538, 122, "yes: post, exempt", 10.5, OK, 600)
    b += line(650, y0 + h, 650, 150, WARN, 1.4, arrow=True)
    b += t(642, 166, "approved: post + daily report to Finance and Compliance", 10.5, WARN, 600, "end")
    b += line(730, y0 + h, 730, 128, RED, 1.4, arrow=True) + t(738, 122, "not approved:", 10.5, RED, 600) + t(738, 136, "refuse", 10.5, RED, 600)
    b += t(8, 22, "Checks run left to right; system compensations are the fees, fee reversals and interest the close posts", 11, MUTED)
    return svg(W, H, b, "Back-valuation gate with maker-checker")


def auth_lifecycle():
    """The three states the model has (solid) and the exits production needs (dashed)."""
    W, H = 760, 262
    b = ""

    def node(x, y, w, h, name, sub, c, cs, dash=""):
        return (rect(x, y, w, h, cs, c, 2, 10, dash) + t(x + w / 2, y + h / 2 - 2, name, 13.5, c, 800, "middle")
                + t(x + w / 2, y + h / 2 + 15, sub, 10.5, INK2, 400, "middle"))
    b += f"<circle cx='26' cy='134' r='8' fill='{INK}'/>"
    b += line(35, 134, 140, 134, INK2, 1.8, arrow=True) + t(86, 116, "after hold", 10, INK2, 600, "middle") + t(86, 128, "≥ 0", 10, INK2, 600, "middle")
    b += node(142, 100, 150, 68, "APPROVED", "hold reduces available", ACC, ACCS)
    b += curve("M26 143 C 26 205, 70 226, 140 226", RED) + t(40, 182, "after hold < 0", 10, RED, 600)
    b += node(142, 196, 150, 60, "DECLINED", "final; never re-approved", RED, REDS)
    b += line(292, 134, 418, 134, OK, 1.8, arrow=True) + t(355, 124, "matching", 10.5, OK, 700, "middle") + t(355, 152, "settlement", 10.5, OK, 700, "middle")
    b += node(420, 100, 150, 68, "SETTLED", "hold released", OK, OKS)
    b += node(420, 6, 150, 52, "EXPIRED", "needs a hold TTL", OLD, "#fff", "6 4")
    b += curve("M190 98 C 200 40, 300 32, 418 32", OLD, 1.5, "6 4")
    b += node(600, 6, 152, 52, "VOIDED", "merchant reversal", OLD, "#fff", "6 4")
    b += curve("M292 108 C 400 78, 560 80, 640 60", OLD, 1.5, "6 4")
    b += t(600, 200, "dashed = not modelled,", 10.5, MUTED, 600) + t(600, 215, "needed before production", 10.5, MUTED, 600)
    return svg(W, H, b, "Authorization lifecycle")


# -- README figures: these replay the stream, so every number on them comes from the ledger ----------------------
def _ledger_views():
    import sys
    sys.path.insert(0, ROOT)
    from ledger.core import Ledger
    from ledger.stream import ACCOUNTS, STREAM
    from replay import run

    def replay_until(event_id):
        led = Ledger(ACCOUNTS)
        for ev in STREAM:
            led.apply(ev)
            if ev.id == event_id:
                return led
        raise KeyError(event_id)
    final, day5 = run(), replay_until("E8")
    day5.close_day()
    processed = {}                                  # the day the ledger actually recorded each event
    for e in final.entries:
        if e.event:
            processed.setdefault(e.event, e.booked_day)
    for tr in final.auth_log:
        processed.setdefault(tr.source, tr.booked_day)
    return {
        "STREAM": STREAM, "DAY5": day5, "PROCESSED": processed,
        "PRINTED": [final.reports[d - 1]["accounts"][A1]["closing"] for d in range(1, 7)],
        "TRUTH": [final.balance(A1, d) for d in range(1, 7)],
        "VIEW5": [day5.balance(A1, d) for d in range(1, 6)],
        "PRE5": [day5.balance(A1, d, exclude_fee_day=d) for d in range(1, 6)],
    }


A1 = "ACC-001"
VIO, DEVS = "#6a4c93", "#e3f3f1"
DEV = "#0f766e"


def aed(m, sign=False):
    return ("−" if m < 0 else ("+" if sign and m > 0 else "")) + f"{abs(m) / 100:,.2f}"


def timeline():
    v = _ledger_views()
    STREAM, proc = v["STREAM"], v["PROCESSED"]
    W, H, L0, R0 = 840, 300, 92, 20
    X = lambda d: L0 + (d - 0.5) * (W - L0 - R0) / 6
    ay, vy = 76, 262
    b = t(12, ay - 30, "arrives", 12, INK, 700) + t(12, ay - 15, "(stream order)", 10, MUTED)
    b += t(12, vy + 4, "lands on", 12, INK, 700) + t(12, vy + 19, "(value date)", 10, MUTED)
    for d in range(1, 7):
        b += t(X(d), ay - 28, f"Day {d}", 12, INK2, 700, "middle")
        b += line(X(d) - 52, vy, X(d) + 52, vy, INK2, 2) + t(X(d), vy + 20, f"Day {d}", 11, MUTED, 600, "middle")
    seen = {}
    for ev in STREAM:
        d = proc[ev.id]
        k = seen.get(d, 0)
        seen[d] = k + 1
        multi = sum(1 for v in proc.values() if v == d) > 1
        cx, cy = (X(d) + (k - 0.5) * 56) if multi else X(d), ay + 6
        late, hold = ev.booked_day < d, ev.type == "AUTHORIZATION"
        back = ev.value_day is not None and ev.value_day < d
        c, cs = (RED, REDS) if late else (WARN, WARNS) if back else (DEV, DEVS) if hold else (ACC, ACCS)
        b += rect(cx - 25, cy - 13, 50, 26, cs, c, 1.6) + t(cx, cy + 4, ev.id, 12, c, 800, "middle")
        tag = {"CREDIT": "credit", "DEBIT": "debit", "AUTHORIZATION": "auth", "SETTLEMENT": "settle", "REVERSAL": "reverse"}[ev.type]
        b += t(cx, cy + 27, tag + (" (late)" if late else ""), 9.5, c, 600, "middle")
        if hold:
            b += line(cx, cy + 33, cx, cy + 46, DEV, 1.2, "3 3") + t(cx, cy + 58, "not on ledger", 9, DEV, 600, "middle")
        elif ev.value_day == d:
            b += line(cx, cy + 33, cx, vy - 4, c, 1.4, arrow=True)
        else:
            vx = X(ev.value_day)
            off = 18 if ev.type == "REVERSAL" else -6      # E7 and E9 both land on Day 2: keep their heads apart
            b += curve(f"M{cx:.1f} {cy + 33:.1f} C {cx:.1f} {vy - 40}, {vx + 30:.1f} {vy - 70}, {vx + off:.1f} {vy - 5}", c, 2)
    b += t(W - R0, 22, "E7 and E9 land three and four days back; E10 is booked Day 5 but arrives after E9", 11, RED, 600, "end")
    return svg(W, H, b, "When each event arrives and which day it lands on")


def three_views():
    v = _ledger_views()
    PRINTED, TRUTH, VIEW5 = v["PRINTED"], v["TRUTH"], v["VIEW5"]
    W, H, L0, R0, T0, B0 = 820, 440, 70, 30, 62, 46
    lo, hi = -50000, 75000
    X = lambda d: L0 + (d - 1) * (W - L0 - R0) / 5
    Y = lambda v: T0 + (hi - v) * (H - T0 - B0) / (hi - lo)
    b = rect(L0, Y(0), W - L0 - R0, Y(lo) - Y(0), REDS, rx=0)
    for v in range(lo, hi + 1, 25000):
        b += line(L0, Y(v), W - R0, Y(v), RULE, 1) + t(L0 - 10, Y(v) + 4, aed(v).replace(".00", ""), 11, MUTED, 400, "end")
    b += line(L0, Y(0), W - R0, Y(0), INK2, 1.6)
    for d in range(1, 7):
        b += t(X(d), H - 18, f"Day {d}", 12, INK2, 600, "middle")
    pts = lambda vals: " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in zip(range(1, 7), vals))
    b += f"<polyline points='{pts(PRINTED)}' fill='none' stroke='{OLD}' stroke-width='2' stroke-dasharray='5 5'/>"
    b += f"<polyline points='{pts(VIEW5)}' fill='none' stroke='{RED}' stroke-width='3'/>"
    b += f"<polyline points='{pts(TRUTH)}' fill='none' stroke='{ACC}' stroke-width='3.4'/>"
    for d, v in zip(range(1, 6), VIEW5):
        b += f"<circle cx='{X(d):.1f}' cy='{Y(v):.1f}' r='5' fill='{RED}'/>"
    for d, v in zip(range(1, 7), TRUTH):
        b += f"<circle cx='{X(d):.1f}' cy='{Y(v):.1f}' r='5' fill='{ACC}' stroke='#fff' stroke-width='1.5'/>"
    b += t(X(2) + 8, Y(VIEW5[1]) + 18, aed(VIEW5[1]), 12, RED, 700)
    b += t(X(3), Y(VIEW5[2]) - 14, f"+{aed(VIEW5[2])}: positive, no fee", 12, RED, 700, "middle")
    b += t(X(4) + 8, Y(VIEW5[3]) + 18, aed(VIEW5[3]), 12, RED, 700)
    b += t(X(5), Y(VIEW5[4]) + 24, aed(VIEW5[4]), 13, RED, 800, "middle")
    b += t(X(1) + 6, Y(TRUTH[0]) - 12, aed(TRUTH[0]), 12, ACC, 700)
    b += t(X(3), Y(TRUTH[2]) - 12, aed(TRUTH[2]), 12, ACC, 700, "middle")
    b += t(X(6) - 6, Y(TRUTH[5]) - 12, aed(TRUTH[5]), 13, ACC, 800, "end")
    lx, ly = L0 + 6, 22
    b += line(lx, ly - 4, lx + 26, ly - 4, ACC, 3.4) + t(lx + 32, ly, "final, as known after Day 6", 12, INK, 600)
    b += line(lx + 220, ly - 4, lx + 246, ly - 4, RED, 3) + t(lx + 252, ly, "as the Day 5 close saw it (after E7)", 12, INK, 600)
    b += line(lx + 500, ly - 4, lx + 526, ly - 4, OLD, 2, "5 5") + t(lx + 532, ly, "printed each evening", 12, INK, 600)
    b += t(W - R0, H - 2, "ACC-001, AED. The printed line equals the final one on Days 1-4.", 10.5, MUTED, 400, "end")
    b += rect(lx, ly + 10, 26, 11, REDS, rx=2) + t(lx + 32, ly + 20, "below zero: an overdraft fee is owed for that day", 11.5, RED, 600)
    return svg(W, H, b, "ACC-001 closing balance by day, three views")


def day5_bridge():
    v = _ledger_views()
    DAY5, VIEW5, PRE5 = v["DAY5"], v["VIEW5"], v["PRE5"]
    W, H, L0, R0, T0, B0 = 840, 340, 64, 16, 40, 74
    lo, hi = -50000, 75000
    steps = []
    for d in range(2, 6):
        for e in sorted((e for e in DAY5.entries if e.account == A1 and e.value_day == d), key=lambda e: (e.kind == "FEE", e.seq)):
            if e.kind == "FEE":
                steps.append(("fee", f"test {aed(PRE5[d - 1])}", e.amount, WARN, d))
            else:
                kind = {"DEBIT": "debit", "CREDIT": "credit", "SETTLEMENT": "settle A", "FORCE_POST": "force-post Z"}[e.kind]
                steps.append((e.source, kind, e.amount, OK if e.amount > 0 else RED, d))
    n = len(steps) + 2
    bw = (W - L0 - R0) / n
    Y = lambda v: T0 + (hi - v) * (H - T0 - B0) / (hi - lo)
    b = ""
    for v in range(lo, hi + 1, 25000):
        b += line(L0, Y(v), W - R0, Y(v), RULE, 1) + t(L0 - 8, Y(v) + 4, aed(v).replace(".00", ""), 10.5, MUTED, 400, "end")
    b += line(L0, Y(0), W - R0, Y(0), INK2, 1.6)
    b += t(W - R0, 14, "fee bars: 'test' is that day's balance before its own fee; a fee is owed when it is negative.", 10.5, MUTED, 400, "end")
    b += t(W - R0, 28, f"Day 3 tests at +{aed(VIEW5[2])}, so it gets no fee.", 10.5, MUTED, 400, "end")

    def bar(i, a, z, colour, top, sub, val, strong=False):
        x = L0 + i * bw + bw * 0.14
        y1, y2 = Y(max(a, z)), Y(min(a, z))
        out = rect(x, y1, bw * 0.72, max(y2 - y1, 2.5), colour, rx=3)
        out += t(x + bw * 0.36, y1 - 6 if z >= a else y2 + 15, val, 12 if strong else 11, INK if strong else colour, 800 if strong else 700, "middle")
        out += t(x + bw * 0.36, H - B0 + 18, top, 11, INK, 700, "middle") + t(x + bw * 0.36, H - B0 + 33, sub, 10, MUTED, 400, "middle")
        return out
    total = VIEW5[0]
    b += bar(0, 0, total, ACC, "Day 1", "closing", aed(total), True)
    prev = None
    for i, (lab, sub, delta, colour, day) in enumerate(steps, start=1):
        if day != prev:
            x = L0 + i * bw
            b += line(x, T0 - 6, x, H - B0 + 40, RULE, 1, "3 3") + t(x + 4, H - 8, f"value Day {day}", 10.5, ACC, 700)
            prev = day
        b += bar(i, total, total + delta, colour, lab, sub, aed(delta, True))
        b += line(L0 + i * bw + bw * 0.86, Y(total + delta), L0 + (i + 1) * bw + bw * 0.14, Y(total + delta), MUTED, 1, "2 2")
        total += delta
    assert total == VIEW5[4]
    b += bar(n - 1, 0, total, RED, "Day 5", "closing", aed(total), True)
    return svg(W, H, b, "Bridge from Day 1 closing to Day 5 closing at the Day 5 close")


FIGURES = {"close-cost": close_cost, "backvalue-gate": backvalue_gate, "auth-lifecycle": auth_lifecycle,
           "timeline": timeline, "three-views": three_views, "day5-bridge": day5_bridge}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in FIGURES.items():
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as fh:
            fh.write(fn())
        print("wrote", f"docs/img/{name}.svg")
