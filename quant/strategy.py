"""Three-vote trend strategy for QQQ (manual execution).

Bull market = at least 2 of 3 votes:
  1. SMA200 band: on above SMA200 x 1.01, off below SMA200 x 0.98 (otherwise unchanged)
  2. Faber: last month-end close above the average of the last 10 month-end closes
  3. 12-month momentum: 252-day return above the T-bill return over the same days
Bull: QQQ exposure = 35% / 20-day volatility, rounded to 0.5 / 1 / 1.5 (QLD for >1).
Bear: 0.5 if MA7 > MA25 or MTUM beat USMV over 20 days; else -0.5 (PSQ) if SMA200 is
      lower than 20 days ago; else 0.
Money not in QQQ/QLD/PSQ stays in T-bills (SGOV).
Exposure increases are taken at the weekly check (last session of the week); decreases
are taken on any day. Orders execute at the next open.

Usage: python quant/strategy.py          backtest summary
       python quant/strategy.py today    what to hold after the latest close
"""

import math
import sys
from datetime import date

from core import Market, backtest, metrics, read, realized_vol, sma

LEVELS = (0.5, 1.0, 1.5)
FEAR_GREED = ((25, "极度恐惧"), (45, "恐惧"), (55, "中性"), (75, "贪婪"), (101, "极度贪婪"))


def signals(m):
    a, n = m.adj["QQQ"], m.n
    ma7, ma25, ma200 = sma(a, 7), sma(a, 25), sma(a, 200)
    vol = realized_vol(a, 20)

    band, state = [None] * n, 0.0
    for i in range(199, n):
        state = 1.0 if a[i] > ma200[i] * 1.01 else 0.0 if a[i] < ma200[i] * 0.98 else state
        band[i] = state

    faber, closes, state = [None] * n, [], None
    for i in range(n):
        if i + 1 < n and m.dates[i][:7] != m.dates[i + 1][:7]:
            closes.append(a[i])
            if len(closes) >= 10:
                state = 1.0 if a[i] > sum(closes[-10:]) / 10 else 0.0
        faber[i] = state

    momentum = [None] * n
    for i in range(252, n):
        cash = math.prod(1 + m.cash[k] for k in range(i - 252, i)) - 1
        momentum[i] = 1.0 if a[i] / a[i - 252] - 1 > cash else 0.0

    def ret20(s, i):
        return m.adj[s][i] / m.adj[s][i - 20] - 1

    bull = [None if None in v else sum(v) >= 2 for v in zip(band, faber, momentum)]
    return {
        "bull": bull, "band": band, "faber": faber, "momentum": momentum, "vol": vol, "ma200": ma200,
        "cross": [i >= 24 and ma7[i] > ma25[i] for i in range(n)],
        "factor": [i >= 20 and bool(m.adj["MTUM"][i - 20]) and ret20("MTUM", i) > ret20("USMV", i) for i in range(n)],
        "falling": [i >= 219 and ma200[i] < ma200[i - 20] for i in range(n)],
    }


def target(sig, i):
    if sig["bull"][i]:
        return min(LEVELS, key=lambda lv: abs(lv - min(LEVELS[-1], 0.35 / sig["vol"][i])))
    if sig["cross"][i] or sig["factor"][i]:
        return 0.5
    return -0.5 if sig["falling"][i] else 0.0


def weights(m, sig=None):
    sig = sig or signals(m)
    weekly = {i for i in range(m.n - 1)
              if date.fromisoformat(m.dates[i]).isocalendar()[:2] != date.fromisoformat(m.dates[i + 1]).isocalendar()[:2]}
    qqq, held = [0.0] * m.n, 0.0
    for i in range(m.n):
        if sig["bull"][i] is None:
            continue
        want = target(sig, i)
        if i in weekly or want < held:
            held = want
        qqq[i] = held
    return {"QQQ": qqq}


def allocation(q):
    parts = {"QQQ": min(q, 2 - q) if q > 0 else 0, "QLD": max(q - 1, 0), "PSQ": max(-q, 0)}
    parts["SGOV"] = 1 - sum(parts.values())
    return " + ".join(f"{v:.0%} {k}" for k, v in parts.items() if v > 1e-9)


def today(m):
    sig, i = signals(m), m.n - 1
    w = weights(m, sig)
    now, before = allocation(w["QQQ"][i]), allocation(w["QQQ"][i - 1])
    yes = lambda x: "是" if x else "否"
    print(f"数据截至 {m.dates[i]}；QQQ 收盘 {m.close[i]:.2f}，200 日均线 {sig['ma200'][i]:.2f}，20 日波动 {sig['vol'][i]:.1%}")
    print(f"牛市投票：均线带 {yes(sig['band'][i])}，10 个月均线 {yes(sig['faber'][i])}，12 个月动量 {yes(sig['momentum'][i])}"
          f" → {'牛市' if sig['bull'][i] else '熊市'}")
    print(f"熊市信号：MA7>MA25 {yes(sig['cross'][i])}，MTUM>USMV {yes(sig['factor'][i])}，200 日均线下行 {yes(sig['falling'][i])}")
    print(f"目标持仓：{now}")
    print("操作：无需调整" if now == before else f"操作：下一交易日开盘由 {before} 调整为 {now}")
    fg = read("FEAR_GREED")
    day = max(d for d in fg if d <= m.dates[i])
    value = float(fg[day]["fear_greed"])
    label = next(name for top, name in FEAR_GREED if value < top)
    print(f"贪婪恐惧指数（仅供参考，不参与决策）：{value:.0f}，{label}（{day}）")


if __name__ == "__main__":
    market = Market()
    if sys.argv[1:] == ["today"]:
        today(market)
    else:
        w = weights(market)
        for start, end in (("2020-01-02", "2026-12-31"), ("2005-01-03", "2019-12-31"),
                           ("2000-01-03", "2004-12-31"), ("2000-01-03", "2026-12-31")):
            r = metrics(backtest(market, w, start, end))
            print(f"{start[:4]}-{end[:4]}: CAGR {r['cagr']:+.1%}  max drawdown {r['max_drawdown']:+.1%}  growth x{r['growth']:.2f}")
