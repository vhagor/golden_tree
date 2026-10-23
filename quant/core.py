"""Shared data, indicators, backtest engine and metrics.

Conventions: a target weight decided at the close of day i is traded at the open of day
i+1; trades cost 5 bp of the amount traded; idle cash earns the 13-week T-bill rate;
exposure above 100% is QLD-like (T-bill + 2%/yr); short exposure is PSQ-like (0.95%/yr).
"""

import csv
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COST, LEVERAGE_SPREAD, SHORT_FEE = 0.0005, 0.02, 0.0095


def read(symbol):
    with (ROOT / "data" / f"{symbol}.csv").open() as f:
        return {r["date"]: r for r in csv.DictReader(f)}


class Market:
    """QQQ trading calendar with other series aligned and forward-filled."""

    def __init__(self, symbols=("MTUM", "USMV")):
        qqq = read("QQQ")
        self.dates = sorted(qqq)
        self.n = len(self.dates)
        self.close = [float(qqq[d]["close"]) for d in self.dates]
        self.adj = {"QQQ": [float(qqq[d]["adjusted_close"]) for d in self.dates]}
        self.adj_open = {"QQQ": [float(qqq[d]["open"]) * a / c
                                 for d, a, c in zip(self.dates, self.adj["QQQ"], self.close)]}
        for s in symbols:
            rows = self.aligned(s)
            self.adj[s] = [r and float(r["adjusted_close"]) for r in rows]
            self.adj_open[s] = [r and float(r["open"]) * float(r["adjusted_close"]) / float(r["close"]) for r in rows]
        self.cash = [r and float(r["close"]) / 100 / 252 for r in self.aligned("IRX")]

    def aligned(self, symbol):
        raw, last, out = read(symbol), None, []
        for d in self.dates:
            last = raw.get(d, last)
            out.append(last)
        return out


def sma(values, n):
    out = [None] * len(values)
    for i in range(n - 1, len(values)):
        out[i] = sum(values[i - n + 1:i + 1]) / n
    return out


def realized_vol(values, n):
    logs = [0.0] + [math.log(values[i] / values[i - 1]) for i in range(1, len(values))]
    return [None if i < n else statistics.pstdev(logs[i - n + 1:i + 1]) * math.sqrt(252) for i in range(len(values))]


def backtest(m, weights, start, end):
    """weights: {symbol: [target weight decided at each close]}. Returns [(date, equity)]."""
    days = [i for i, d in enumerate(m.dates) if start <= d <= end]
    held = {s: 0.0 for s in weights}
    equity, curve = 1.0, []
    for i in days:
        rate = m.cash[i - 1]
        longs = sum(max(w, 0) for w in held.values())
        shorts = sum(max(-w, 0) for w in held.values())
        financing = (1 - longs) * rate if longs <= 1 else (1 - longs) * (rate + LEVERAGE_SPREAD / 252)
        overnight = sum(w * (m.adj_open[s][i] / m.adj[s][i - 1] - 1) for s, w in held.items() if w)
        equity *= 1 + overnight + financing - shorts * SHORT_FEE / 252
        target = {s: weights[s][i - 1] for s in weights}
        equity *= 1 - COST * sum(abs(target[s] - held[s]) for s in weights)
        equity *= 1 + sum(w * (m.adj[s][i] / m.adj_open[s][i] - 1) for s, w in target.items() if w)
        held = target
        curve.append((m.dates[i], equity))
    return curve


def period(default_start="2020-01-02"):
    """[start] [end] from the command line."""
    args = sys.argv[1:] + [default_start, "2099-12-31"][len(sys.argv[1:]):]
    return args[0], args[1]


def metrics(curve):
    values = [1.0] + [e for _, e in curve]
    years = len(curve) / 252
    peak, drawdown = 1.0, 0.0
    for v in values:
        peak = max(peak, v)
        drawdown = min(drawdown, v / peak - 1)
    return {"growth": values[-1], "cagr": values[-1] ** (1 / years) - 1, "max_drawdown": drawdown}
