#!/usr/bin/env python3
"""Rate Lab weekly price refresh.

Pulls the latest prices from the Sector Teardown feed (which itself refreshes
every trading day after the US close) and updates site/data/lab.json in place.
Only the price side moves: fair-value inputs stay anchored to the October 19,
2026 models, so implied upsides drift with the market between visits.

Run by .github/workflows/refresh.yml; can also be run locally:
    python3 refresh_prices.py
Author: Archit Chawla.
"""

import json
import urllib.request
from pathlib import Path

FEED_URL = "https://architchawla26.github.io/Sector-Teardown-20/data/companies.json"
LAB_JSON = Path(__file__).resolve().parent / "site" / "data" / "lab.json"


def main():
    with urllib.request.urlopen(FEED_URL, timeout=60) as fh:
        feed = json.load(fh)
    prices = {c["ticker"]: c for c in feed["companies"]}

    lab = json.loads(LAB_JSON.read_text())
    changed = 0
    for company in lab["companies"]:
        src = prices.get(company["ticker"])
        if src is None:
            continue
        if company["price"] != src["price"] or company["price_asof"] != src["price_asof"]:
            company["price"] = src["price"]
            company["price_asof"] = src["price_asof"]
            changed += 1
    lab["meta"]["price_asof"] = feed["meta"]["price_asof"]
    LAB_JSON.write_text(json.dumps(lab, indent=1))
    print(f"Updated {changed} prices; price_asof = {feed['meta']['price_asof']}")


if __name__ == "__main__":
    main()
