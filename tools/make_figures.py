"""Draw the figures used by the documents into docs/img/*.svg.

    python3 tools/make_figures.py

Standard library only. The architecture figures are diagrams of the design; none of them restates the
event stream.
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
    """What one end-of-day close re-walks today, and after the snapshot + dirty-from change."""
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
        o += t(x0, 62 + accts * ch + 16, "day 1", 10, MUTED) + t(x0 + (days - 1) * cw + cw - 3, 62 + accts * ch + 16, f"day {days}", 10, MUTED, 400, "end")
        return o
    b += grid(56, "Today: every close re-tests every day of every account",
              "cost ≈ accounts × days × entries (balance() scans the whole log)", lambda a, d: True)
    b += grid(446, "After: daily snapshots + a dirty-from mark per account",
              "cost ≈ touched accounts × days since the earliest back-value", lambda a, d: (a == 1 and d >= 3) or (a == 3 and d >= 9))
    b += t(446 + 3 * cw, 56, "▼ back-value lands on day 4", 10.5, RED, 700)
    return svg(W, H, b, "Close cost before and after the snapshot change")


def backvalue_gate():
    """The one control before go-live."""
    W, H = 760, 150
    b = ""
    boxes = [(8, 150, "entry arrives", "value date vs business date", SOFT, INK2),
             (186, 168, "value date < today?", "system compensations exempt", ACCS, ACC),
             (382, 160, "reason code + checker", "a second person approves", WARNS, WARN),
             (570, 182, "inside a sealed period?", "yes: refuse, post today", REDS, RED)]
    for x, w, n, s, cs, c in boxes:
        b += rect(x, 14, w, 58, cs, c, 1.6, 8) + t(x + 10, 38, n, 12.5, c, 700) + t(x + 10, 57, s, 10.5, INK2)
    b += line(158, 43, 184, 43, INK2, 1.6, arrow=True)
    b += line(354, 43, 380, 43, INK2, 1.6, arrow=True) + t(367, 34, "yes", 10, MUTED, 600, "middle")
    b += line(542, 43, 568, 43, INK2, 1.6, arrow=True)
    b += rect(382, 98, 370, 44, OKS, OK, 1.4, 8)
    b += t(394, 117, "every back-valued entry → daily report to Finance + Compliance", 11, OK, 650)
    b += t(394, 133, "with its fee and interest impact per customer", 10.5, INK2)
    b += line(462, 72, 462, 96, OK, 1.4, arrow=True)
    return svg(W, H, b, "Back-valuation gate with maker-checker")


def auth_lifecycle():
    """States the model has (solid) and the exits production needs (dashed)."""
    W, H = 760, 250
    b = ""

    def node(x, y, w, h, name, sub, c, cs, dash=""):
        return (rect(x, y, w, h, cs, c, 2, 10, dash) + t(x + w / 2, y + h / 2 - 2, name, 13.5, c, 800, "middle")
                + t(x + w / 2, y + h / 2 + 15, sub, 10.5, INK2, 400, "middle"))
    b += f"<circle cx='26' cy='118' r='8' fill='{INK}'/>"
    b += line(35, 118, 104, 118, INK2, 1.8, arrow=True) + t(70, 108, "authorize", 10.5, MUTED, 600, "middle")
    b += node(106, 84, 150, 68, "APPROVED", "hold reduces available", ACC, ACCS)
    b += curve("M30 126 C 40 200, 70 214, 104 214", RED) + t(8, 168, "available < 0", 10, RED, 600)
    b += node(106, 182, 150, 60, "DECLINED", "final; never re-approved", RED, REDS)
    b += line(256, 118, 364, 118, OK, 1.8, arrow=True) + t(310, 108, "matching", 10.5, OK, 700, "middle") + t(310, 136, "settlement", 10.5, OK, 700, "middle")
    b += node(366, 84, 150, 68, "SETTLED", "hold released", OK, OKS)
    b += node(366, 6, 150, 56, "EXPIRED", "needs a hold TTL", OLD, "#fff", "6 4")
    b += curve("M200 82 C 220 34, 280 32, 364 32", OLD, 1.5, "6 4")
    b += node(560, 6, 192, 56, "VOIDED", "merchant / timeout reversal", OLD, "#fff", "6 4")
    b += curve("M256 100 C 400 76, 480 54, 558 38", OLD, 1.5, "6 4")
    b += node(560, 182, 192, 60, "FORCE_POST", "post + EXCEPTION for review", WARN, WARNS)
    b += curve("M540 150 C 580 160, 620 166, 650 180", WARN)
    b += t(530, 146, "settlement with no approved authorization", 10.5, WARN, 600)
    b += t(560, 100, "dashed = not modelled,", 10.5, MUTED, 600) + t(560, 115, "needed before production", 10.5, MUTED, 600)
    return svg(W, H, b, "Authorization lifecycle")


FIGURES = {"close-cost": close_cost, "backvalue-gate": backvalue_gate, "auth-lifecycle": auth_lifecycle}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in FIGURES.items():
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as fh:
            fh.write(fn())
        print("wrote", f"docs/img/{name}.svg")
