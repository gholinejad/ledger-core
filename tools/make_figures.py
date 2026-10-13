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


FIGURES = {"close-cost": close_cost, "backvalue-gate": backvalue_gate, "auth-lifecycle": auth_lifecycle}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in FIGURES.items():
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as fh:
            fh.write(fn())
        print("wrote", f"docs/img/{name}.svg")
