"""Account snapshot: equity, positions, stops, today's fills.

Usage:
    python -m portfolio.snapshot

Writes output/runs/<date>/snapshot_<HHMM>.json and prints a table.
Used by the midday, end-of-day, and weekly routines.
"""

import json
import sys
from datetime import date, datetime

from dotenv import load_dotenv

from . import broker, config


def take() -> dict:
    acct = broker.account()
    equity = float(acct.equity)
    last_equity = float(acct.last_equity)  # equity at previous close

    stops = {}
    for o in broker.open_orders():
        if str(o.order_type).endswith("trailing_stop") or getattr(o, "trail_percent", None):
            stops[o.symbol] = float(o.trail_percent) if o.trail_percent else None

    positions = []
    for p in broker.positions():
        positions.append(
            {
                "ticker": p.symbol,
                "qty": int(float(p.qty)),
                "avg_entry": float(p.avg_entry_price),
                "current": float(p.current_price),
                "market_value": float(p.market_value),
                "weight": round(float(p.market_value) / equity, 4),
                "unrealized_pl_pct": round(float(p.unrealized_plpc) * 100, 2),
                "unrealized_pl_usd": round(float(p.unrealized_pl), 2),
                "trail_pct": stops.get(p.symbol),
            }
        )

    fills = [
        {
            "ticker": o.symbol,
            "side": str(o.side).split(".")[-1].lower(),
            "type": str(o.order_type).split(".")[-1].lower(),
            "qty": int(float(o.filled_qty)),
            "avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
            "filled_at": o.filled_at.isoformat(),
        }
        for o in broker.todays_filled_orders()
    ]

    return {
        "taken_at": datetime.now().isoformat(timespec="seconds"),
        "equity": equity,
        "cash": float(acct.cash),
        "day_pl_usd": round(equity - last_equity, 2),
        "day_pl_pct": round((equity / last_equity - 1) * 100, 2) if last_equity else 0.0,
        "positions": sorted(positions, key=lambda p: -p["market_value"]),
        "todays_fills": fills,
        "positions_missing_stop": [p["ticker"] for p in positions if p["trail_pct"] is None],
    }


def main() -> None:
    load_dotenv()
    try:
        snap = take()
    except RuntimeError as e:
        sys.exit(str(e))

    run_dir = config.RUNS_DIR / date.today().isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M")
    path = run_dir / f"snapshot_{stamp}.json"
    path.write_text(json.dumps(snap, indent=2))

    print(f"equity ${snap['equity']:,.2f}  cash ${snap['cash']:,.2f}  "
          f"day P&L {snap['day_pl_usd']:+,.2f} ({snap['day_pl_pct']:+.2f}%)")
    for p in snap["positions"]:
        trail = f"trail {p['trail_pct']}%" if p["trail_pct"] else "NO STOP"
        print(f"  {p['ticker']:<6} {p['qty']:>5} @ {p['avg_entry']:<8.2f} now {p['current']:<8.2f} "
              f"{p['unrealized_pl_pct']:+6.2f}%  w {p['weight']*100:4.1f}%  {trail}")
    if snap["todays_fills"]:
        print("today's fills:")
        for f in snap["todays_fills"]:
            print(f"  {f['side'].upper():<4} {f['ticker']:<6} x{f['qty']} @ {f['avg_price']}")
    if snap["positions_missing_stop"]:
        print(f"WARNING — positions without trailing stop: {', '.join(snap['positions_missing_stop'])}")
    print(f"snapshot written to {path}")


if __name__ == "__main__":
    main()
