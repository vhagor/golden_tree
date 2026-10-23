"""Draw the strategy against QQQ as an SVG: one-time $10,000, monthly $1,000, and drawdown.

Usage: python quant/plot.py [start] [end]      (defaults 2000-01-03 .. latest)
Output: reports/comparison_<start year>.svg
"""

import math

from core import ROOT, Market, period
from dca import accumulate
from lump_sum import run

W, LEFT, RIGHT = 1200, 90, 1060
COLORS = {"strategy": "#2a78d6", "qqq": "#eb6834", "paid": "#898781"}
NAMES = {"strategy": "Three-vote strategy", "qqq": "QQQ", "paid": "Money paid in"}


def panel(svg, top, height, title, series, log, fmt, end_labels=True):
    values = [v for pts in series.values() for _, v in pts]
    f = math.log10 if log else (lambda v: v)
    lo, hi = f(min(values)), f(max(values))
    y = lambda v: top + height - (f(v) - lo) / (hi - lo) * height
    n = len(next(iter(series.values())))
    x = lambda k: LEFT + k * (RIGHT - LEFT) / (n - 1)
    svg.append(f'<text x="{LEFT}" y="{top - 14}" font-size="16" font-weight="600">{title}</text>')
    for t in range(5):
        v = lo + t * (hi - lo) / 4
        v = 10 ** v if log else v
        svg.append(f'<line x1="{LEFT}" x2="{RIGHT}" y1="{y(v):.0f}" y2="{y(v):.0f}" stroke="#e1e0d9"/>'
                   f'<text x="{LEFT - 8}" y="{y(v) + 4:.0f}" font-size="12" fill="#898781" text-anchor="end">{fmt(v)}</text>')
    for name, pts in series.items():
        line = " ".join(f"{x(k):.0f},{y(v):.0f}" for k, (_, v) in enumerate(pts) if k % 2 == 0 or k == n - 1)
        svg.append(f'<polyline points="{line}" fill="none" stroke="{COLORS[name]}" stroke-width="2"/>')
        if end_labels:
            svg.append(f'<text x="{RIGHT + 8}" y="{y(pts[-1][1]) + 4:.0f}" font-size="12">{fmt(pts[-1][1])}</text>')
    return x, n


def drawdown(pts):
    peak, out = 0.0, []
    for d, v in pts:
        peak = max(peak, v)
        out.append((d, v / peak - 1))
    return out


if __name__ == "__main__":
    start, end = period("2000-01-03")
    curves = run(Market(), start, end)
    lump = {k: [(d, 10_000 * e) for d, e in c] for k, c in curves.items()}
    monthly = {k: accumulate(c) for k, c in curves.items()}
    dca = {k: [(d, v) for d, _, v in p] for k, p in monthly.items()}
    dca["paid"] = [(d, paid) for d, paid, _ in monthly["qqq"]]
    money = lambda v: f"${v:,.0f}"

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="1060" font-family="system-ui, sans-serif">',
           f'<rect width="{W}" height="1060" fill="#fcfcfb"/>',
           f'<text x="{LEFT}" y="40" font-size="22" font-weight="600">Three-vote strategy vs QQQ, {start} to {lump["qqq"][-1][0]}</text>']
    for k, name in enumerate(NAMES):
        svg.append(f'<line x1="{LEFT + k * 220}" x2="{LEFT + k * 220 + 24}" y1="66" y2="66" stroke="{COLORS[name]}" stroke-width="3"/>'
                   f'<text x="{LEFT + k * 220 + 32}" y="70" font-size="13">{NAMES[name]}</text>')
    panel(svg, 120, 280, "One-time $10,000 (log scale)", lump, True, money)
    panel(svg, 470, 280, "$1,000 every month (log scale)", dca, True, money)
    x, n = panel(svg, 820, 180, "Drawdown of the one-time investment",
                 {k: drawdown(v) for k, v in lump.items()}, False, lambda v: f"{v:.0%}", end_labels=False)
    dates = [d for d, _ in lump["qqq"]]
    for k in range(0, n, max(1, n // 12)):
        svg.append(f'<text x="{x(k):.0f}" y="1030" font-size="12" fill="#898781" text-anchor="middle">{dates[k][:7]}</text>')
    svg.append("</svg>")
    out = ROOT / "reports" / f"comparison_{start[:4]}.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(svg))
    print(f"saved {out}")
