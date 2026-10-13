"""Money is stored as integer minor units (fils for AED, fils for BHD).

AED has 2 decimal places (1 AED = 100 fils), BHD has 3 (1 BHD = 1000 fils).
Integers make addition exact; Decimal is used only where a rate is applied,
and the result is rounded back to an integer immediately.
"""
from decimal import Decimal, ROUND_HALF_EVEN

PRECISION = {"AED": 2, "BHD": 3}


def to_minor(amount: str, ccy: str) -> int:
    """Parse a decimal string like '1200.00' into minor units. Refuses sub-unit input."""
    scaled = Decimal(amount).scaleb(PRECISION[ccy])
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{amount} has more than {PRECISION[ccy]} decimals for {ccy}")
    return int(scaled)


def fmt(minor: int, ccy: str) -> str:
    """Format minor units as '1,200.00 AED' / '-370.00 AED'."""
    value = Decimal(minor).scaleb(-PRECISION[ccy])
    return f"{value:,.{PRECISION[ccy]}f} {ccy}"


def apply_rate(minor: int, rate: Decimal) -> int:
    """minor * rate, rounded half-even to a whole minor unit."""
    return int((Decimal(minor) * rate).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def split_evenly(total_minor: int, parts: int) -> list[int]:
    """Split into `parts` amounts that sum exactly to the total.

    Every part is total // parts; the last part absorbs the remainder:
    10.000 BHD / 3 -> 3.333, 3.333, 3.334.
    """
    base, remainder = divmod(total_minor, parts)
    return [base] * (parts - 1) + [base + remainder]
