"""Execute the allocation plan on the Alpaca paper account.

Usage:
    python -m portfolio.execute --dry-run   # print intended orders only
    python -m portfolio.execute             # place paper orders

Order flow per plan:
  1. Reconcile: watchlist 'held' tickers no longer in Alpaca positions were
     closed by their trailing stops -> mark stopped_out (starts cooldown).
  2. Sells first (swap displacements): cancel the old trailing stop, market
     sell, wait for fill.
  3. Buys: whole-share market order, wait for fill, then GTC trailing-stop
     sell at the plan's trail_pct; mark watchlist 'held'.
"""

import argparse
import json
import sys
from datetime import date

from dotenv import load_dotenv

from research import watchlist

from . import broker, config


def reconcile(live_symbols: set[str]) -> list[str]:
    """Mark watchlist entries whose positions disappeared as stopped_out."""
    stopped = []
    for e in watchlist.load():
        if e.get("status") == "held" and e["ticker"] not in live_symbols:
            watchlist.set_status(e["ticker"], "stopped_out")
            stopped.append(e["ticker"])
    return stopped


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Execute allocation plan on Alpaca paper")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--run-dir", default=str(config.RUNS_DIR / date.today().isoformat())
    )
    args = parser.parse_args()

    from pathlib import Path

    plan_path = Path(args.run_dir) / "allocation_plan.json"
    if not plan_path.exists():
        sys.exit(f"no allocation plan at {plan_path} — run: python -m portfolio.sizing")
    plan = json.loads(plan_path.read_text())

    try:
        live = {p.symbol: p for p in broker.positions()}
    except RuntimeError as e:
        sys.exit(str(e))
    stopped = reconcile(set(live))
    if stopped:
        print(f"stop-outs detected (cooldown starts): {', '.join(stopped)}")

    sells = [a for a in plan["actions"] if a["action"] == "sell"]
    buys = [a for a in plan["actions"] if a["action"] == "buy"]
    report = {"date": date.today().isoformat(), "dry_run": args.dry_run, "orders": []}

    for a in sells:
        t = a["ticker"]
        qty = int(float(live[t].qty)) if t in live else 0
        print(f"SELL {t} x{qty} ({a['reason']})")
        if not args.dry_run and qty:
            broker.cancel_open_orders(t)
            order = broker.sell_market(t, qty)
            broker.wait_for_fill(order.id)
            watchlist.set_status(t, "watch")
        report["orders"].append({"ticker": t, "side": "sell", "qty": qty})

    for a in buys:
        t, shares, trail = a["ticker"], a["est_shares"], a["trail_pct"]
        if not shares:
            print(f"SKIP {t}: no share count (missing current_price)")
            continue
        print(f"BUY  {t} x{shares} (~${a['dollars']:,.0f}, {a['weight']*100:.1f}%) "
              f"+ trailing stop {trail}%")
        if not args.dry_run:
            order = broker.buy_market(t, shares)
            filled = broker.wait_for_fill(order.id)
            filled_qty = int(float(filled.filled_qty))
            broker.trailing_stop(t, filled_qty, trail)
            watchlist.set_status(t, "held")
            report["orders"].append(
                {"ticker": t, "side": "buy", "qty": filled_qty,
                 "avg_price": float(filled.filled_avg_price), "trail_pct": trail}
            )
        else:
            report["orders"].append(
                {"ticker": t, "side": "buy", "qty": shares, "trail_pct": trail}
            )

    report_path = Path(args.run_dir) / "execution_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    mode = "DRY RUN — no orders placed" if args.dry_run else "orders placed on Alpaca paper"
    print(f"\n{mode}; report at {report_path}")


if __name__ == "__main__":
    main()
