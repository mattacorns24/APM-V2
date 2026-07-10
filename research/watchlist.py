"""Persistent watchlist of scored ideas at output/watchlist.json.

Entry fields: ticker, company, thesis, conviction, date, and (when research
produced targets) current_price, upside_pct, downside_pct, reward_risk.
Portfolio lifecycle fields: status ("watch" | "held" | "stopped_out"),
stopped_at (date the trailing stop fired).
"""

import json
from datetime import date, timedelta

from . import config


def load() -> list[dict]:
    if not config.WATCHLIST_PATH.exists():
        return []
    return json.loads(config.WATCHLIST_PATH.read_text())


def tickers() -> set[str]:
    return {entry["ticker"] for entry in load()}


def add(entries: list[dict]) -> None:
    """Add scored ideas to the watchlist. Dedupes by ticker, keeping the
    newest entry. Fresh research resets status to 'watch' (clears cooldown)."""
    existing = {e["ticker"]: e for e in load()}
    today = date.today().isoformat()
    for entry in entries:
        existing[entry["ticker"]] = {
            "status": "watch",
            **entry,
            "date": entry.get("date", today),
        }
    _save(list(existing.values()))


def set_status(ticker: str, status: str) -> None:
    """Mark an entry held / stopped_out / watch. stopped_out stamps stopped_at."""
    entries = load()
    for e in entries:
        if e["ticker"] == ticker:
            e["status"] = status
            if status == "stopped_out":
                e["stopped_at"] = date.today().isoformat()
            else:
                e.pop("stopped_at", None)
    _save(entries)


def eligible(cooldown_days: int) -> list[dict]:
    """Entries eligible for new allocation: not held, and either never stopped
    out or past the cooldown window."""
    cutoff = date.today() - timedelta(days=cooldown_days)
    out = []
    for e in load():
        if e.get("status") == "held":
            continue
        if e.get("status") == "stopped_out":
            if date.fromisoformat(e["stopped_at"]) > cutoff:
                continue
        out.append(e)
    return out


def _save(entries: list[dict]) -> None:
    config.WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.WATCHLIST_PATH.write_text(
        json.dumps(sorted(entries, key=lambda e: -e["conviction"]), indent=2)
    )


if __name__ == "__main__":
    entries = load()
    if not entries:
        print("watchlist empty")
    for e in entries:
        status = e.get("status", "watch")
        rr = e.get("reward_risk", "n/a")
        print(
            f"{e['ticker']:<6} conv {e['conviction']:>3}  rr {rr!s:<5} "
            f"{status:<12} {e['date']}  {e['thesis']}"
        )
