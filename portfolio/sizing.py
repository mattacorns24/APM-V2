"""Deterministic position sizing: conviction x reward/risk -> allocation plan.

Pure math in build_plan() (no I/O); the CLI wires it to the watchlist and
Alpaca account state.

Usage:
    python -m portfolio.sizing               # live account snapshot from Alpaca
    python -m portfolio.sizing --plan-only   # no broker: assume flat $100k account
"""

import argparse
import json
from datetime import date

from research import watchlist

from . import config


def attractiveness(entry: dict) -> float | None:
    """conviction * min(reward_risk, cap). None if entry can't be sized
    (missing targets or non-positive reward/risk)."""
    rr = entry.get("reward_risk")
    if rr is None:
        return None
    if rr <= 0:
        return None
    return entry["conviction"] * min(rr, config.ATTRACT_RR_CAP)


def trail_pct(weight: float) -> float:
    lo, hi = config.TRAIL_CLAMP
    return round(max(lo, min(hi, config.RISK_BUDGET / weight * 100)), 1)


def build_plan(candidates: list[dict], held: dict[str, float], equity: float, cash: float) -> dict:
    """candidates: eligible watchlist entries. held: ticker -> current weight.
    Returns plan dict with buy/sell/hold/skip actions.

    Buy-only + swap: held positions are never trimmed. New candidates deploy
    free cash (above the MIN_CASH reserve); when cash or position slots run
    out, a candidate may displace the weakest holding if its attractiveness
    beats it by SWAP_MARGIN.
    """
    actions = []
    skips = []

    scored = []
    for e in candidates:
        if e["conviction"] < config.ENTRY_THRESHOLD:
            skips.append({"ticker": e["ticker"], "reason": f"conviction {e['conviction']} < {config.ENTRY_THRESHOLD}"})
            continue
        a = attractiveness(e)
        if a is None:
            reason = (
                "no price targets — re-research to add them"
                if e.get("reward_risk") is None
                else f"reward/risk {e['reward_risk']} <= 0"
            )
            skips.append({"ticker": e["ticker"], "reason": reason})
            continue
        scored.append({**e, "attract": a})
    scored.sort(key=lambda e: -e["attract"])

    for t, w in held.items():
        actions.append({"ticker": t, "action": "hold", "weight": round(w, 4)})

    # Attractiveness of current holdings (from their watchlist entries) for swaps
    held_attract = {}
    for e in watchlist.load():
        if e["ticker"] in held:
            held_attract[e["ticker"]] = attractiveness(e) or 0.0

    deployable = max(0.0, cash - config.MIN_CASH * equity)
    slots = config.MAX_POSITIONS - len(held)
    total_attract = sum(e["attract"] for e in scored)

    for e in scored:
        raw_weight = (e["attract"] / total_attract) if total_attract else 0.0
        weight = max(config.MIN_WEIGHT, min(config.MAX_WEIGHT, raw_weight))
        dollars = weight * equity

        if slots > 0 and dollars <= deployable:
            actions.append(_buy(e, weight, dollars))
            deployable -= dollars
            slots -= 1
            continue

        # No room — try displacing the weakest holding
        swap_out = min(held_attract, key=held_attract.get) if held_attract else None
        if swap_out is not None and e["attract"] >= config.SWAP_MARGIN * held_attract[swap_out]:
            freed = held[swap_out] * equity
            weight = min(weight, (deployable + freed) / equity)
            if weight >= config.MIN_WEIGHT:
                actions.append(
                    {"ticker": swap_out, "action": "sell",
                     "reason": f"displaced by {e['ticker']} "
                               f"(attract {e['attract']:.0f} >= {config.SWAP_MARGIN} x {held_attract[swap_out]:.0f})"}
                )
                buy = _buy(e, weight, weight * equity)
                buy["funded_by_sale_of"] = swap_out
                actions.append(buy)
                deployable = max(0.0, deployable + freed - weight * equity)
                del held_attract[swap_out]
                continue

        reason = "cash below reserve" if slots > 0 else "portfolio full"
        skips.append({"ticker": e["ticker"], "reason": f"{reason}; swap margin not met"})

    return {
        "date": date.today().isoformat(),
        "equity": equity,
        "cash": cash,
        "actions": actions,
        "skipped": skips,
    }


def _buy(entry: dict, weight: float, dollars: float) -> dict:
    return {
        "ticker": entry["ticker"],
        "action": "buy",
        "weight": round(weight, 4),
        "dollars": round(dollars, 2),
        "est_shares": int(dollars // entry["current_price"]) if entry.get("current_price") else None,
        "trail_pct": trail_pct(weight),
        "attract": round(entry["attract"], 1),
        "conviction": entry["conviction"],
        "reward_risk": entry["reward_risk"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute allocation plan")
    parser.add_argument("--plan-only", action="store_true",
                        help="assume a flat $100k account; do not contact Alpaca")
    args = parser.parse_args()

    if args.plan_only:
        equity, cash, held = 100_000.0, 100_000.0, {}
    else:
        from . import broker

        acct = broker.account()
        equity, cash = float(acct.equity), float(acct.cash)
        held = {
            p.symbol: float(p.market_value) / equity for p in broker.positions()
        }

    candidates = watchlist.eligible(config.COOLDOWN_DAYS)
    candidates = [c for c in candidates if c["ticker"] not in held]
    plan = build_plan(candidates, held, equity, cash)

    run_dir = config.RUNS_DIR / date.today().isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "allocation_plan.json").write_text(json.dumps(plan, indent=2))

    print(f"equity ${equity:,.0f}  cash ${cash:,.0f}\n")
    for a in plan["actions"]:
        if a["action"] == "buy":
            print(f"  BUY  {a['ticker']:<6} {a['weight']*100:>5.1f}%  ${a['dollars']:>10,.0f}  "
                  f"trail {a['trail_pct']}%  (attract {a['attract']})")
        elif a["action"] == "sell":
            print(f"  SELL {a['ticker']:<6} {a['reason']}")
        else:
            print(f"  HOLD {a['ticker']:<6} {a['weight']*100:>5.1f}%")
    for s in plan["skipped"]:
        print(f"  SKIP {s['ticker']:<6} {s['reason']}")
    print(f"\nplan written to {run_dir / 'allocation_plan.json'}")


if __name__ == "__main__":
    main()
