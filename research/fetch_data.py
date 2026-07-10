"""Free financial data via yfinance: quarterly revenue, YoY growth, trend.

Usage:
    python -m research.fetch_data NVDA

Prints JSON. YoY is computed against the same quarter one year earlier where
yfinance history allows; quarters without a prior-year match get
revenue_yoy_pct: null (fill those from web research, labeled source "web").
"""

import json
import sys

import pandas as pd
import yfinance as yf

QUARTERS_REPORTED = 4  # how many recent quarters to emit
YOY_MATCH_TOLERANCE_DAYS = 45  # prior-year quarter-end date wiggle room


def fetch(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    stmt = t.quarterly_income_stmt
    if stmt is None or stmt.empty or "Total Revenue" not in stmt.index:
        raise ValueError(f"No quarterly revenue data for '{ticker}'")

    revenue = stmt.loc["Total Revenue"].dropna()  # index: period-end dates, newest first
    dates = sorted(revenue.index)  # oldest first

    quarters = []
    for d in dates[-QUARTERS_REPORTED:]:
        yoy = None
        target = d - pd.Timedelta(days=365)
        for prior in dates:
            if prior < d and abs((prior - target).days) <= YOY_MATCH_TOLERANCE_DAYS:
                if revenue[prior]:
                    yoy = round((revenue[d] / revenue[prior] - 1) * 100, 1)
                break
        quarters.append(
            {
                "quarter": f"FQ ending {d.date().isoformat()}",
                "revenue": int(revenue[d]),
                "revenue_yoy_pct": yoy,
                "source": "yfinance",
            }
        )

    info = t.info or {}
    return {
        "ticker": ticker.upper(),
        "company": info.get("longName") or info.get("shortName") or ticker.upper(),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "quarters": quarters,
        "trend": _classify_trend([q["revenue_yoy_pct"] for q in quarters]),
        "note": (
            "revenue_yoy_pct is null where yfinance lacks the prior-year quarter; "
            "fill those from web research and mark source as 'web'."
        ),
    }


def _classify_trend(yoy_values: list) -> str:
    known = [v for v in yoy_values if v is not None]
    if len(known) < 2:
        return "unknown"
    if all(b > a for a, b in zip(known, known[1:])):
        return "accelerating"
    if all(b < a for a, b in zip(known, known[1:])):
        return "decelerating"
    return "mixed"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m research.fetch_data TICKER")
    try:
        print(json.dumps(fetch(sys.argv[1]), indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e), "ticker": sys.argv[1].upper()}))
        sys.exit(1)


if __name__ == "__main__":
    main()
