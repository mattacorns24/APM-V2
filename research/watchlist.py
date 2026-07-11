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
    newest entry. Fresh research resets status to 'watch' (clears cooldown) —
    unless the position is currently held, whose status and midday-action
    history must survive re-research."""
    existing = {e["ticker"]: e for e in load()}
    today = date.today().isoformat()
    for entry in entries:
        prior = existing.get(entry["ticker"], {})
        carried = {}
        if prior.get("status") == "held":
            carried = {
                "status": "held",
                **{k: prior[k] for k in ("midday_steps", "last_midday_action") if k in prior},
            }
        existing[entry["ticker"]] = {
            "status": "watch",
            **entry,
            "date": entry.get("date", today),
            **carried,
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


def midday_history(ticker: str) -> dict:
    """Midday-action history for a ticker: {'steps': [...], 'last_action': iso|None}."""
    for e in load():
        if e["ticker"] == ticker:
            return {"steps": e.get("midday_steps", []),
                    "last_action": e.get("last_midday_action")}
    return {"steps": [], "last_action": None}


def record_midday_step(ticker: str, step: str) -> None:
    """Append a fired midday step (e.g. 'trim_-5', 'tighten_15') and stamp today."""
    entries = load()
    for e in entries:
        if e["ticker"] == ticker:
            e.setdefault("midday_steps", []).append(step)
            e["last_midday_action"] = date.today().isoformat()
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
