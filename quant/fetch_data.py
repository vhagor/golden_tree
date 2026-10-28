"""Download daily prices from Yahoo Finance into data/<SYMBOL>.csv, and the CNN Fear & Greed
index (display only, from a public daily archive) into data/FEAR_GREED.csv.

Usage: python quant/fetch_data.py [SYMBOL ...]
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from strategy import SYMBOLS as PORTFOLIO

DATA = Path(__file__).resolve().parents[1] / "data"
SYMBOLS = ["QQQ", "^IRX", *PORTFOLIO]
FEAR_GREED_URL = "https://raw.githubusercontent.com/whit3rabbit/fear-greed-data/main/fear-greed.csv"


def fetch(symbol):
    end = int(datetime.now(timezone.utc).timestamp())
    url = (f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol.replace('^', '%5E')}"
           f"?period1=921024000&period2={end}&interval=1d&events=div%2Csplits")
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
        result = json.load(r)["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    adjusted = result["indicators"].get("adjclose", [{"adjclose": quote["close"]}])[0]["adjclose"]
    rows = []
    for t, o, c, a in zip(result["timestamp"], quote["open"], quote["close"], adjusted):
        if None not in (o, c, a):
            rows.append([datetime.fromtimestamp(t, timezone.utc).date().isoformat(), o, c, a])
    return rows


def fetch_fear_greed():
    with urlopen(Request(FEAR_GREED_URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
        rows = list(csv.DictReader(r.read().decode().splitlines()))
    return [[row["Date"], row["Fear Greed"]] for row in rows]


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    for symbol in sys.argv[1:] or SYMBOLS:
        rows = fetch(symbol)
        with (DATA / f"{symbol.lstrip('^')}.csv").open("w", newline="") as f:
            csv.writer(f).writerows([["date", "open", "close", "adjusted_close"], *rows])
        print(f"{symbol}: {len(rows)} days, {rows[0][0]} .. {rows[-1][0]}")
    if not sys.argv[1:]:
        rows = fetch_fear_greed()
        with (DATA / "FEAR_GREED.csv").open("w", newline="") as f:
            csv.writer(f).writerows([["date", "fear_greed"], *rows])
        print(f"Fear & Greed: {len(rows)} days, {rows[0][0]} .. {rows[-1][0]}")
