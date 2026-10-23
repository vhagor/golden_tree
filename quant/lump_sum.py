"""One-time investment: everything into QQQ at the start versus the strategy.

Usage: python quant/lump_sum.py [start] [end]      (defaults 2020-01-02 .. latest)
"""

from core import Market, backtest, metrics, period
from strategy import weights


def run(m, start, end):
    return {"strategy": backtest(m, weights(m), start, end),
            "qqq": backtest(m, {"QQQ": [1.0] * m.n}, start, end)}


if __name__ == "__main__":
    start, end = period()
    for name, curve in run(Market(), start, end).items():
        r = metrics(curve)
        print(f"{name:8s} $10,000 -> ${10_000 * r['growth']:,.0f}  CAGR {r['cagr']:+.1%}  max drawdown {r['max_drawdown']:+.1%}")
