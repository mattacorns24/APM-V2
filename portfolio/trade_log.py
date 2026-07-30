"""Persistent log of executed new-position buys at output/trade_log.json.

Backs the weekly trade cap (MAX_NEW_TRADES_PER_WEEK): every filled buy that
opens a position — including swap-funded buys — is recorded here. Sells,
stop-outs, and midday trims are never logged. The file lives in output/ so
it rides the private data repo and survives across cloud sessions.

Week key is ISO (Monday reset), matching the trading week.
"""

import json
from datetime import date

from . import config

TRADE_LOG_PATH = config.OUTPUT_DIR / "trade_log.json"


def load() -> list[dict]:
    if not TRADE_LOG_PATH.exists():
        return []
    return json.loads(TRADE_LOG_PATH.read_text())


def week_key(d: date | None = None) -> str:
    d = d or date.today()
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def record_buy(ticker: str, qty: int, price: float | None = None) -> None:
    entries = load()
    entries.append(
        {
            "ticker": ticker,
            "side": "buy",
            "qty": qty,
            "price": price,
            "date": date.today().isoformat(),
            "week": week_key(),
        }
    )
    TRADE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRADE_LOG_PATH.write_text(json.dumps(entries, indent=2))


def buys_this_week(today: date | None = None) -> int:
    wk = week_key(today)
    return sum(1 for e in load() if e["side"] == "buy" and e.get("week") == wk)


def remaining_this_week(today: date | None = None) -> int:
    return max(0, config.MAX_NEW_TRADES_PER_WEEK - buys_this_week(today))
