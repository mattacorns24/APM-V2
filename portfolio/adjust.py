"""Execute planned midday actions: cancel stop -> act -> re-place stop.

Usage:
    python -m portfolio.adjust [--dry-run]

Reads midday_review.json (written by portfolio.review). Actions:
- trim:    cancel stop, market-sell trim qty, wait fill, re-place trailing
           stop on the remaining qty at the SAME trail %
- tighten: cancel stop, re-place trailing stop on full qty at new trail %
- close:   cancel stop, market-sell all, mark stopped_out (30-day cooldown)

A position must never be left uncovered: stop re-placement is attempted even
when the sell leg fails, and any re-place failure is flagged loudly in the
execution report.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from research import watchlist

from . import broker, config


def run_action(a: dict, dry_run: bool) -> dict:
    result = {**a, "status": "dry_run" if dry_run else "pending", "warnings": []}
    if dry_run:
        return result

    t = a["ticker"]
    try:
        broker.cancel_open_orders(t)

        if a["action"] == "close":
            order = broker.sell_market(t, a["qty"])
            broker.wait_for_fill(order.id)
            watchlist.set_status(t, "stopped_out")
            result["status"] = "done"

        elif a["action"] == "trim":
            sell_failed = False
            try:
                order = broker.sell_market(t, a["qty"])
                broker.wait_for_fill(order.id)
            except Exception as e:  # noqa: BLE001 — must still re-cover the position
                sell_failed = True
                result["warnings"].append(f"trim sell failed: {e}")
            remaining = a["remaining_qty"] if not sell_failed else a["qty"] + a["remaining_qty"]
            trail = a["trail_pct"]
            try:
                broker.trailing_stop(t, remaining, trail)
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(
                    f"STOP RE-PLACEMENT FAILED — {t} x{remaining} is UNCOVERED: {e}"
                )
                result["status"] = "failed"
                return result
            result["status"] = "done" if not sell_failed else "partial"

        elif a["action"] == "tighten":
            try:
                broker.trailing_stop(t, a["qty"], a["new_trail"])
            except Exception as e:  # noqa: BLE001
                result["warnings"].append(
                    f"STOP RE-PLACEMENT FAILED — {t} x{a['qty']} is UNCOVERED: {e}"
                )
                result["status"] = "failed"
                return result
            result["status"] = "done"

        if result["status"] in ("done", "partial"):
            watchlist.record_midday_step(t, a["step"])

    except Exception as e:  # noqa: BLE001 — per-ticker isolation
        result["status"] = "failed"
        result["warnings"].append(str(e))
    return result


def main() -> None:
    load_dotenv()
    if not config.MIDDAY_RULES_ENABLED:
        sys.exit("MIDDAY_RULES_ENABLED is False — adjust refuses to run")

    parser = argparse.ArgumentParser(description="Execute midday trim/tighten actions")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--run-dir", default=str(config.RUNS_DIR / date.today().isoformat())
    )
    args = parser.parse_args()

    review_path = Path(args.run_dir) / "midday_review.json"
    if not review_path.exists():
        sys.exit(f"no review at {review_path} — run: python -m portfolio.review")
    review = json.loads(review_path.read_text())
    actions = review.get("planned_actions", [])

    results = [run_action(a, args.dry_run) for a in actions]
    report = {"date": date.today().isoformat(), "dry_run": args.dry_run, "results": results}
    report_path = Path(args.run_dir) / "midday_execution.json"
    report_path.write_text(json.dumps(report, indent=2))

    if not results:
        print("no actions to execute")
    for r in results:
        line = f"{r['action'].upper():<7} {r['ticker']:<6} [{r['status']}] {r['reason']}"
        print(line)
        for w in r["warnings"]:
            print(f"  !! {w}")
    print(f"execution report at {report_path}")

    if any(r["status"] == "failed" for r in results):
        sys.exit(2)


if __name__ == "__main__":
    main()
