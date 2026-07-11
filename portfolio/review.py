"""Midday decision engine: trim losers, tighten winner stops.

Usage:
    python -m portfolio.review

Rules (portfolio/config.py):
- Loser ladder: P&L <= -5% -> sell 25% of qty; <= -8% -> sell 50% of remainder.
  Each step once per position, ever. The trailing stop stays as the final exit.
- Winner ratchet: gain >= +15% -> trail x0.75; >= +30% -> trail x0.5.
  Floor 4%, never loosens, highest crossed step wins.
- Guardrails: skip positions bought today; one action per position per day;
  max 3 actions per run (closes, then trims worst-first, then tightens);
  a trim leaving < 2% weight becomes a full close (starts cooldown).

Writes output/runs/<date>/midday_review.json with planned_actions.
portfolio/adjust.py executes them.
"""

import json
import sys
from datetime import date

from dotenv import load_dotenv

from research import watchlist

from . import config, sizing, snapshot


def decide(snap: dict, todays_buy_tickers: set[str]) -> tuple[list[dict], list[dict]]:
    """Returns (actions, skips). Pure given a snapshot dict + today's buys."""
    actions, skips = [], []
    today = date.today().isoformat()

    for p in snap["positions"]:
        t = p["ticker"]
        pl = p["unrealized_pl_pct"]
        hist = watchlist.midday_history(t)

        if t in todays_buy_tickers:
            skips.append({"ticker": t, "reason": "opened today — exempt until tomorrow"})
            continue
        if hist["last_action"] == today:
            skips.append({"ticker": t, "reason": "already acted on today"})
            continue

        # Loser ladder — deepest crossed, unfired step
        loser_action = None
        for threshold, fraction in sorted(config.LOSER_TRIM_STEPS):  # deepest first
            step = f"trim_{threshold:g}"
            if pl <= threshold and step not in hist["steps"]:
                trim_qty = max(1, round(p["qty"] * fraction))
                remaining_value = (p["qty"] - trim_qty) * p["current"]
                if remaining_value < config.DUST_WEIGHT * snap["equity"] or trim_qty >= p["qty"]:
                    loser_action = {"ticker": t, "action": "close", "qty": p["qty"],
                                    "step": step, "pnl_pct": pl,
                                    "reason": f"P&L {pl:+.1f}% <= {threshold:g}%; trim would leave "
                                              f"< {config.DUST_WEIGHT*100:.0f}% weight — closing (cooldown)"}
                else:
                    loser_action = {"ticker": t, "action": "trim", "qty": trim_qty,
                                    "remaining_qty": p["qty"] - trim_qty,
                                    "trail_pct": p["trail_pct"], "step": step, "pnl_pct": pl,
                                    "reason": f"P&L {pl:+.1f}% <= {threshold:g}% — sell "
                                              f"{fraction*100:.0f}% of qty ({trim_qty} sh)"}
                break
        if loser_action:
            actions.append(loser_action)
            continue

        # Winner ratchet — highest crossed, unfired step
        for threshold, mult in sorted(config.WINNER_TIGHTEN_STEPS, reverse=True):
            step = f"tighten_{threshold:g}"
            if pl >= threshold and step not in hist["steps"]:
                current_trail = p["trail_pct"]
                if current_trail is None:
                    # missing stop — re-place at the sizing formula's trail
                    new_trail = sizing.trail_pct(p["weight"])
                    actions.append({"ticker": t, "action": "tighten", "qty": p["qty"],
                                    "new_trail": new_trail, "step": step, "pnl_pct": pl,
                                    "reason": f"gain {pl:+.1f}% >= {threshold:g}% but NO STOP FOUND — "
                                              f"placing trail {new_trail}%"})
                    break
                new_trail = max(config.TRAIL_FLOOR, round(current_trail * mult, 1))
                if new_trail >= current_trail:
                    skips.append({"ticker": t, "reason": f"gain {pl:+.1f}% but trail already "
                                                         f"{current_trail}% <= computed {new_trail}% (ratchet/floor)"})
                    break
                actions.append({"ticker": t, "action": "tighten", "qty": p["qty"],
                                "old_trail": current_trail, "new_trail": new_trail,
                                "step": step, "pnl_pct": pl,
                                "reason": f"gain {pl:+.1f}% >= {threshold:g}% — trail "
                                          f"{current_trail}% -> {new_trail}%"})
                break

    # Priority: closes, trims (worst P&L first), tightens (biggest gain first); cap
    order = {"close": 0, "trim": 1, "tighten": 2}
    actions.sort(key=lambda a: (order[a["action"]],
                                a["pnl_pct"] if a["action"] != "tighten" else -a["pnl_pct"]))
    if len(actions) > config.MAX_MIDDAY_ACTIONS:
        for dropped in actions[config.MAX_MIDDAY_ACTIONS:]:
            skips.append({"ticker": dropped["ticker"],
                          "reason": f"max {config.MAX_MIDDAY_ACTIONS} actions/run — deferred"})
        actions = actions[: config.MAX_MIDDAY_ACTIONS]

    return actions, skips


def main() -> None:
    load_dotenv()
    try:
        snap = snapshot.take()
        from . import broker

        todays_buys = {o.symbol for o in broker.todays_filled_orders()
                       if str(o.side).endswith("buy")}
    except RuntimeError as e:
        sys.exit(str(e))

    if config.MIDDAY_RULES_ENABLED:
        actions, skips = decide(snap, todays_buys)
    else:
        actions, skips = [], [{"ticker": "*", "reason": "MIDDAY_RULES_ENABLED=False"}]

    result = {
        "rules_enabled": config.MIDDAY_RULES_ENABLED,
        "snapshot": snap,
        "planned_actions": actions,
        "skips": skips,
    }
    run_dir = config.RUNS_DIR / date.today().isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "midday_review.json"
    path.write_text(json.dumps(result, indent=2))

    if actions:
        for a in actions:
            print(f"PLAN {a['action'].upper():<7} {a['ticker']:<6} {a['reason']}")
    else:
        print("no actions planned")
    for s in skips:
        print(f"skip {s['ticker']:<6} {s['reason']}")
    print(f"review written to {path}")


if __name__ == "__main__":
    main()
