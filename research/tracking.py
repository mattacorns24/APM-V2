"""Shadow-track every scored ticker vs SPY to find the optimal conviction cutoff.

Every ticker research.score grades is recorded here — traded or not — with its
conviction and price at research date. `update` fills the 30/60/90-day price
horizons (ticker and SPY closes via yfinance) as they come due; `analyze`
sweeps candidate conviction cutoffs and reports average alpha + win rate above
each. Report-only: it never changes the live entry cutoff in portfolio config.

Usage:
    python -m research.tracking update    # fill due horizons (EOD routine)
    python -m research.tracking analyze   # cutoff sweep report (weekly routine)
    python -m research.tracking show      # dump raw tracking entries

All commands accept --file PATH to operate on an alternate tracking file
(backtests); analyze also accepts --min-sample N. Defaults = live config
values, so the routine CLIs are unchanged. A horizon due exactly today only
fills after the market close — re-run update post-close if it stays empty.

State: output/conviction_tracking.json (list of entries)
    {"ticker", "research_date", "conviction", "price", "spy", "horizons":
        {"30": {"due", "price", "spy", "return_pct", "spy_return_pct", "alpha_pct"}, ...}}
Analysis report: output/conviction_analysis.json
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

from . import config


def load(path: Path | None = None) -> list:
    path = path or config.TRACKING_PATH
    if path.exists():
        return json.loads(path.read_text())
    return []


def save(entries: list, path: Path | None = None) -> None:
    path = path or config.TRACKING_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))


def record(
    ticker: str,
    conviction: int,
    price: float,
    research_date: str | None = None,
    path: Path | None = None,
) -> None:
    """Upsert an entry keyed on (ticker, research_date). Called by research.score,
    so a same-day re-score updates in place instead of duplicating."""
    d = research_date or date.today().isoformat()
    entries = load(path)
    for e in entries:
        if e["ticker"] == ticker and e["research_date"] == d:
            e["conviction"] = conviction
            e["price"] = price
            break
    else:
        entries.append(
            {
                "ticker": ticker,
                "research_date": d,
                "conviction": conviction,
                "price": price,
                "spy": None,
                "horizons": {},
            }
        )
    save(entries, path)


def _close_on_or_after(symbol: str, day: date, cache: dict) -> float | None:
    """First daily close on or after `day` (handles weekends/holidays)."""
    key = (symbol, day.isoformat())
    if key not in cache:
        import yfinance as yf

        hist = yf.Ticker(symbol).history(
            start=day.isoformat(), end=(day + timedelta(days=7)).isoformat()
        )
        cache[key] = round(float(hist["Close"].iloc[0]), 2) if not hist.empty else None
    return cache[key]


def update(path: Path | None = None) -> None:
    """Fill every due, still-empty horizon. Failed fetches stay empty and are
    retried on the next run."""
    entries = load(path)
    today = date.today()
    cache: dict = {}
    filled = 0
    for e in entries:
        rdate = date.fromisoformat(e["research_date"])
        if e.get("spy") is None:
            e["spy"] = _close_on_or_after(config.BENCHMARK, rdate, cache)
        for h in config.TRACK_HORIZONS:
            k = str(h)
            if k in e["horizons"] or rdate + timedelta(days=h) > today:
                continue
            due = rdate + timedelta(days=h)
            px = _close_on_or_after(e["ticker"], due, cache)
            spy_px = _close_on_or_after(config.BENCHMARK, due, cache)
            if px is None or spy_px is None or not e.get("spy"):
                continue
            ret = (px / e["price"] - 1) * 100
            spy_ret = (spy_px / e["spy"] - 1) * 100
            e["horizons"][k] = {
                "due": due.isoformat(),
                "price": px,
                "spy": spy_px,
                "return_pct": round(ret, 2),
                "spy_return_pct": round(spy_ret, 2),
                "alpha_pct": round(ret - spy_ret, 2),
            }
            filled += 1
    save(entries, path)
    print(f"tracking: {len(entries)} entries, filled {filled} horizon(s)")


def analyze(path: Path | None = None, min_sample: int | None = None) -> None:
    entries = load(path)
    min_sample = min_sample if min_sample is not None else config.MIN_CUTOFF_SAMPLE
    analysis_path = config.ANALYSIS_PATH if path is None else path.with_name("analysis.json")
    if not entries:
        print("no tracking entries yet — nothing to analyze")
        return

    report = {
        "generated": date.today().isoformat(),
        "n_entries": len(entries),
        "horizons": {},
        "recommendation": None,
    }
    for h in config.TRACK_HORIZONS:
        k = str(h)
        obs = [
            (e["conviction"], e["horizons"][k]["alpha_pct"])
            for e in entries
            if k in e.get("horizons", {})
        ]
        if not obs:
            continue
        sweep = []
        for cutoff in config.CUTOFF_SWEEP:
            above = [a for c, a in obs if c >= cutoff]
            below = [a for c, a in obs if c < cutoff]
            sweep.append(
                {
                    "cutoff": cutoff,
                    "n_above": len(above),
                    "avg_alpha_above": round(mean(above), 2) if above else None,
                    "win_rate_above": round(100 * sum(a > 0 for a in above) / len(above), 1)
                    if above
                    else None,
                    "n_below": len(below),
                    "avg_alpha_below": round(mean(below), 2) if below else None,
                }
            )
        report["horizons"][k] = {"n_observations": len(obs), "sweep": sweep}

    # recommend from the longest horizon with a big-enough sample: the cutoff
    # whose above-group has the best average alpha
    for h in sorted((int(k) for k in report["horizons"]), reverse=True):
        candidates = [
            r
            for r in report["horizons"][str(h)]["sweep"]
            if r["n_above"] >= min_sample and r["avg_alpha_above"] is not None
        ]
        if candidates:
            best = max(candidates, key=lambda r: r["avg_alpha_above"])
            report["recommendation"] = {
                "horizon_days": h,
                "cutoff": best["cutoff"],
                "avg_alpha_above": best["avg_alpha_above"],
                "win_rate_above": best["win_rate_above"],
                "n_above": best["n_above"],
            }
            break

    analysis_path.write_text(json.dumps(report, indent=2))

    for k, hdata in report["horizons"].items():
        print(f"\n{k}-day horizon ({hdata['n_observations']} observations)")
        print("cutoff | n>= | avg alpha | win rate | n< | avg alpha<")
        for r in hdata["sweep"]:
            print(
                f"{r['cutoff']:>6} | {r['n_above']:>3} | "
                f"{r['avg_alpha_above'] if r['avg_alpha_above'] is not None else 'n/a':>9} | "
                f"{str(r['win_rate_above']) + '%' if r['win_rate_above'] is not None else 'n/a':>8} | "
                f"{r['n_below']:>3} | {r['avg_alpha_below'] if r['avg_alpha_below'] is not None else 'n/a'}"
            )

    rec = report["recommendation"]
    if rec:
        print(
            f"\nrecommended cutoff: conviction >= {rec['cutoff']} "
            f"({rec['horizon_days']}-day avg alpha {rec['avg_alpha_above']:+.2f}%, "
            f"win rate {rec['win_rate_above']}%, n={rec['n_above']})"
        )
    else:
        print(
            f"\nno recommendation yet — need >= {min_sample} filled "
            f"entries above a cutoff"
        )
    print("report-only: the live entry cutoff in portfolio config is unchanged")
    print(f"report written to {analysis_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Conviction-cutoff tracking")
    parser.add_argument("command", choices=["update", "analyze", "show"])
    parser.add_argument(
        "--file", type=Path, default=None,
        help="tracking file (default: live conviction_tracking.json)",
    )
    parser.add_argument(
        "--min-sample", type=int, default=None,
        help="analyze only: min entries above a cutoff to recommend",
    )
    args = parser.parse_args()
    if args.command == "update":
        update(args.file)
    elif args.command == "analyze":
        analyze(args.file, args.min_sample)
    else:
        print(json.dumps(load(args.file), indent=2))


if __name__ == "__main__":
    main()
