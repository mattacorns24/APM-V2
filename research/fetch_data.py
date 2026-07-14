"""Free financial data via yfinance: quarterly revenue, YoY growth, trend.

Usage:
    python -m research.fetch_data NVDA
    python -m research.fetch_data NVDA --as-of 2026-04-15

Prints JSON. YoY is computed against the same quarter one year earlier where
yfinance history allows; quarters without a prior-year match get
revenue_yoy_pct: null (fill those from web research, labeled source "web").

--as-of (backtests): only quarters presumed reported by that date are emitted
(period end + REPORTING_LAG_DAYS), price is the close on/before that date, and
market_cap is null. Do NOT backfill later quarters from the web in as-of mode.
"""

import argparse
import json
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from . import config

QUARTERS_REPORTED = 4  # how many recent quarters to emit
YOY_MATCH_TOLERANCE_DAYS = 45  # prior-year quarter-end date wiggle room


def fetch(ticker: str, as_of: date | None = None) -> dict:
    t = yf.Ticker(ticker)
    stmt = t.quarterly_income_stmt
    if stmt is None or stmt.empty or "Total Revenue" not in stmt.index:
        raise ValueError(f"No quarterly revenue data for '{ticker}'")

    revenue = stmt.loc["Total Revenue"].dropna()  # index: period-end dates, newest first
    dates = sorted(revenue.index)  # oldest first
    if as_of is not None:
        # only quarters whose earnings were presumably out by as_of
        dates = [
            d for d in dates
            if d.date() + timedelta(days=config.REPORTING_LAG_DAYS) <= as_of
        ]
        if not dates:
            raise ValueError(f"no quarters reported by {as_of} for '{ticker}'")

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
    if as_of is not None:
        hist = t.history(
            start=(as_of - timedelta(days=7)).isoformat(),
            end=(as_of + timedelta(days=1)).isoformat(),
        )
        if hist.empty:
            raise ValueError(f"no price history at {as_of} for '{ticker}'")
        price = round(float(hist["Close"].iloc[-1]), 2)
        market_cap = None  # today's cap would leak future information
    else:
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        market_cap = info.get("marketCap")

    result = {
        "ticker": ticker.upper(),
        "company": info.get("longName") or info.get("shortName") or ticker.upper(),
        "price": price,
        "market_cap": market_cap,
        "quarters": quarters,
        "trend": _classify_trend([q["revenue_yoy_pct"] for q in quarters]),
        "note": (
            "revenue_yoy_pct is null where yfinance lacks the prior-year quarter; "
            "fill those from web research and mark source as 'web'."
        ),
    }
    if as_of is not None:
        result["as_of"] = as_of.isoformat()
        result["note"] = (
            f"as-of {as_of}: quarters limited to those reported by then "
            f"(period end + {config.REPORTING_LAG_DAYS}d), price is the {as_of} close. "
            "Do not backfill later quarters from the web."
        )
    return result


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
    parser = argparse.ArgumentParser(description="Quarterly revenue + YoY via yfinance")
    parser.add_argument("ticker")
    parser.add_argument(
        "--as-of", default=None, metavar="YYYY-MM-DD",
        help="backtest mode: only quarters reported by this date, price at this date",
    )
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    try:
        print(json.dumps(fetch(args.ticker, as_of=as_of), indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e), "ticker": args.ticker.upper()}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
