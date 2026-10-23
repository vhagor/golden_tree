"""Monthly investing: the same amount on the first session of every month, into QQQ or
into the strategy (new money follows the strategy's current allocation).

Usage: python quant/dca.py [start] [end]      (defaults 2020-01-02 .. latest)
"""

from core import Market, period
from lump_sum import run


def accumulate(curve, amount=1000):
    """Account value over time when `amount` is added each month at that day's price."""
    units, paid, out = 0.0, 0, []
    for k, (day, nav) in enumerate(curve):
        if k == 0 or day[:7] != curve[k - 1][0][:7]:
            units += amount / nav
            paid += amount
        out.append((day, paid, units * nav))
    return out


def irr(flows):
    """Annual money-weighted return; flows = [(years from start, cash flow)]."""
    lo, hi = -0.9, 2.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if sum(f / (1 + mid) ** t for t, f in flows) > 0 else (lo, mid)
    return mid


def summary(path):
    flows, last_paid = [], 0
    worst = min(value / paid - 1 for _, paid, value in path)
    for k, (day, paid, value) in enumerate(path):
        if paid > last_paid:
            flows.append((k / 252, -(paid - last_paid)))
            last_paid = paid
    day, paid, value = path[-1]
    flows.append((len(path) / 252, value))
    return {"paid": paid, "value": value, "irr": irr(flows), "worst_vs_paid": worst}


if __name__ == "__main__":
    start, end = period()
    for name, curve in run(Market(), start, end).items():
        r = summary(accumulate(curve))
        print(f"{name:8s} paid ${r['paid']:,.0f} -> ${r['value']:,.0f}  IRR {r['irr']:+.1%}  "
              f"worst value vs paid {r['worst_vs_paid']:+.1%}")
