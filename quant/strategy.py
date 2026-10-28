"""Portfolio: QQQ + BRK-B + AI stocks, with a three-vote bull/bear switch (manual execution).

Bull market = at least 2 of 3 votes on QQQ:
  1. SMA200 band: on above SMA200 x 1.01, off below SMA200 x 0.98 (otherwise unchanged)
  2. Faber: last month-end close above the average of the last 10 month-end closes
  3. 12-month momentum: 252-day return above the T-bill return over the same days
Holdings (share of the account):
  QQQ                  50%  bull: QQQ, bear: SGOV
  BRK-B                20%  always held
  AI infrastructure    15%  always held, equal weight
  AI growth            15%  bull: equal weight, bear: SGOV
Switching into the bull holdings happens at the weekly check (last session of the week); switching
out happens on any day. Orders execute at the next open. Fixed weights are restored every quarter.

Usage: python quant/strategy.py          backtest summary
       python quant/strategy.py today    what to hold after the latest close
"""

import math
import sys
from datetime import date

from core import Market, backtest, metrics, read, sma

QQQ_SHARE = 0.50
CORE = {"BRK-B": 0.20}
INFRA, INFRA_SHARE = ("PWR", "ETN", "HUBB", "EQIX", "DLR", "CSCO"), 0.15
GROWTH, GROWTH_SHARE = ("TSM", "KLAC", "LRCX", "AMAT", "ANET", "VRT", "DELL", "CIEN", "MRVL"), 0.15
SYMBOLS = (*CORE, *INFRA, *GROWTH)
FEAR_GREED = ((25, "极度恐惧"), (45, "恐惧"), (55, "中性"), (75, "贪婪"), (101, "极度贪婪"))


def signals(m):
    a, n = m.adj["QQQ"], m.n
    ma200 = sma(a, 200)

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

    bull = [None if None in v else sum(v) >= 2 for v in zip(band, faber, momentum)]
    return {"bull": bull, "band": band, "faber": faber, "momentum": momentum, "ma200": ma200, "month_ends": closes}


def risk_on(m, sig):
    """1 while the bull holdings are on: turned on at the weekly check, off on any day."""
    weekly = {i for i in range(m.n - 1)
              if date.fromisoformat(m.dates[i]).isocalendar()[:2] != date.fromisoformat(m.dates[i + 1]).isocalendar()[:2]}
    on, held = [0.0] * m.n, 0.0
    for i in range(m.n):
        want = 1.0 if sig["bull"][i] else 0.0
        if i in weekly or want < held:
            held = want
        on[i] = held
    return on


def weights(m, sig=None):
    on = risk_on(m, sig or signals(m))
    w = {s: [0.0] * m.n for s in ("QQQ", *SYMBOLS)}
    for i in range(m.n):
        w["QQQ"][i] = QQQ_SHARE * on[i]
        for s, share in CORE.items():
            w[s][i] = share if m.adj[s][i] else 0.0
        for group, share, scale in ((INFRA, INFRA_SHARE, 1.0), (GROWTH, GROWTH_SHARE, on[i])):
            live = [s for s in group if m.adj[s][i]]
            for s in live:
                w[s][i] = share / len(live) * scale
    return w


def today(m):
    sig, i = signals(m), m.n - 1
    w = weights(m, sig)
    k = m.close[i] / m.adj["QQQ"][i]
    yes = lambda x: "是" if x else "否"
    hold = lambda j: {s: v[j] for s, v in w.items() if v[j] > 1e-9}
    now, before = hold(i), hold(i - 1)
    cash = math.prod(1 + m.cash[j] for j in range(i - 251, i + 1)) - 1
    print(f"数据截至 {m.dates[i]}；QQQ 收盘 {m.close[i]:.2f}，200 日均线 {sig['ma200'][i] * k:.2f}")
    print(f"牛市投票：均线带 {yes(sig['band'][i])}，10 个月均线 {yes(sig['faber'][i])}，12 个月动量 {yes(sig['momentum'][i])}"
          f" → {'牛市' if sig['bull'][i] else '熊市'}")
    print(f"转熊参考线：收盘低于 {sig['ma200'][i] * 0.98 * k:.2f} 时均线带转熊；月底收盘低于 "
          f"{sum(sig['month_ends'][-9:]) / 9 * k:.2f} 时 10 个月均线转熊；低于 {m.adj['QQQ'][i - 251] * (1 + cash) * k:.2f} 时动量转熊")
    sgov = 1 - sum(now.values())
    print("目标持仓：" + "，".join(f"{s} {v:.1%}" for s, v in now.items()) + (f"，SGOV {sgov:.1%}" if sgov > 0.0005 else ""))
    if now.keys() == before.keys():
        print("操作：无需调整")
    else:
        print("操作：下一交易日开盘" + ("买入 QQQ 和 AI 成长股（卖出相应 SGOV）" if "QQQ" in now else "卖出 QQQ 和 AI 成长股，转入 SGOV"))
    if m.dates[i][:7] != m.dates[i - 1][:7] and m.dates[i][5:7] in ("01", "04", "07", "10"):
        print("再平衡：今天是本季度第一个交易日，请把各项持仓调回目标比例")
    fg = read("FEAR_GREED")
    day = max(d for d in fg if d <= m.dates[i])
    value = float(fg[day]["fear_greed"])
    print(f"贪婪恐惧指数（仅供参考，不参与决策）：{value:.0f}，{next(n for top, n in FEAR_GREED if value < top)}（{day}）")


if __name__ == "__main__":
    market = Market(SYMBOLS)
    if sys.argv[1:] == ["today"]:
        today(market)
    else:
        w, qqq = weights(market), {"QQQ": [1.0] * market.n}
        for start, end in (("2020-01-02", "2099-12-31"), ("2005-01-03", "2019-12-31"), ("2022-01-03", "2022-12-31"),
                           ("2007-10-01", "2009-03-31"), ("2005-01-03", "2099-12-31")):
            r, b = metrics(backtest(market, w, start, end)), metrics(backtest(market, qqq, start, end))
            print(f"{start} .. {end[:7]}: portfolio CAGR {r['cagr']:+.1%} max drawdown {r['max_drawdown']:+.1%}"
                  f" | QQQ {b['cagr']:+.1%} {b['max_drawdown']:+.1%}")
