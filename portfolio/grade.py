"""Weekly grade: outcome vs SPY (60%) + process discipline (40%).

Usage:
    python -m portfolio.grade

Outcome: this week's account return (Alpaca portfolio history) minus SPY's
same-window return (yfinance). Process: trailing stops on every position,
cash reserve intact, no cooldown-violating buys, all research had targets.

Writes output/weekly/<ISO-week>-grade.json.
"""

import json
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

from research import config as rconfig
from research import watchlist

from . import broker, config


def week_outcome() -> dict:
    hist = broker.portfolio_history("1W")
    equities = [e for e in hist.equity if e]
    if len(equities) < 2:
        return {"account_return_pct": 0.0, "spy_return_pct": 0.0, "alpha_pct": 0.0,
                "note": "insufficient portfolio history"}
    account_ret = (equities[-1] / equities[0] - 1) * 100

    import yfinance as yf

    spy = yf.Ticker("SPY").history(period="7d")["Close"]
    spy_ret = (spy.iloc[-1] / spy.iloc[0] - 1) * 100 if len(spy) >= 2 else 0.0

    return {
        "account_return_pct": round(account_ret, 2),
        "spy_return_pct": round(float(spy_ret), 2),
        "alpha_pct": round(account_ret - float(spy_ret), 2),
    }


def process_checks() -> list[dict]:
    checks = []

    # 1. Every open position has a trailing stop
    from . import snapshot

    snap = snapshot.take()
    missing = snap["positions_missing_stop"]
    checks.append({"check": "trailing stop on every position", "passed": not missing,
                   "detail": f"missing: {missing}" if missing else "all covered"})

    # 2. Cash reserve intact
    reserve_ok = snap["cash"] >= config.MIN_CASH * snap["equity"]
    checks.append({"check": f"cash reserve >= {config.MIN_CASH*100:.0f}%", "passed": reserve_ok,
                   "detail": f"cash {snap['cash']/snap['equity']*100:.1f}% of equity"})

    # 3. No cooldown violations: held tickers that were stopped_out < COOLDOWN_DAYS
    #    before their (re)entry would have violated — approximate via current state:
    #    a ticker both 'held' and carrying a recent stopped_at is a violation trace.
    violations = []
    cutoff = date.today() - timedelta(days=config.COOLDOWN_DAYS)
    for e in watchlist.load():
        if e.get("status") == "held" and e.get("stopped_at"):
            if date.fromisoformat(e["stopped_at"]) > cutoff:
                violations.append(e["ticker"])
    checks.append({"check": "no cooldown violations", "passed": not violations,
                   "detail": f"violations: {violations}" if violations else "clean"})

    # 4. This week's research all had price targets
    untargeted = []
    monday = date.today() - timedelta(days=date.today().weekday())
    for day_offset in range(5):
        run_dir = rconfig.RUNS_DIR / (monday + timedelta(days=day_offset)).isoformat()
        if not run_dir.exists():
            continue
        for scores_file in sorted(run_dir.glob("*.json")):
            # per-ticker research JSONs have uppercase stems (NVDA.json);
            # ".scores.json" keeps pre-2026-07-14 run dirs gradable
            if not (rconfig.TICKER_STEM_RE.fullmatch(scores_file.stem)
                    or scores_file.name.endswith(".scores.json")):
                continue
            try:
                if "targets" not in json.loads(scores_file.read_text()):
                    untargeted.append(scores_file.name)
            except (json.JSONDecodeError, OSError):
                untargeted.append(scores_file.name)
    checks.append({"check": "all research had price targets", "passed": not untargeted,
                   "detail": f"missing targets: {untargeted}" if untargeted else "all targeted"})

    return checks


def letter(score: float) -> str:
    for cutoff, grade in [(90, "A"), (80, "B"), (70, "C"), (60, "D")]:
        if score >= cutoff:
            return grade
    return "F"


def compute() -> dict:
    outcome = week_outcome()
    checks = process_checks()

    # Outcome component: alpha of +2% -> 100, 0 -> 70, -2% -> 40 (linear, clamped)
    outcome_score = max(0.0, min(100.0, 70 + outcome["alpha_pct"] * 15))
    process_score = 100.0 * sum(c["passed"] for c in checks) / len(checks)
    total = (config.GRADE_OUTCOME_WEIGHT * outcome_score
             + config.GRADE_PROCESS_WEIGHT * process_score)

    return {
        "week": date.today().strftime("%G-W%V"),
        "outcome": outcome,
        "outcome_score": round(outcome_score, 1),
        "process_checks": checks,
        "process_score": round(process_score, 1),
        "total_score": round(total, 1),
        "grade": letter(total),
    }


def main() -> None:
    load_dotenv()
    try:
        result = compute()
    except RuntimeError as e:
        sys.exit(str(e))

    weekly_dir = rconfig.OUTPUT_DIR / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    path = weekly_dir / f"{result['week']}-grade.json"
    path.write_text(json.dumps(result, indent=2))

    o = result["outcome"]
    print(f"week {result['week']}: account {o['account_return_pct']:+.2f}%  "
          f"SPY {o['spy_return_pct']:+.2f}%  alpha {o['alpha_pct']:+.2f}%")
    for c in result["process_checks"]:
        print(f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['check']} — {c['detail']}")
    print(f"outcome {result['outcome_score']} x{config.GRADE_OUTCOME_WEIGHT} + "
          f"process {result['process_score']} x{config.GRADE_PROCESS_WEIGHT} "
          f"= {result['total_score']} -> GRADE {result['grade']}")
    print(f"written to {path}")


if __name__ == "__main__":
    main()
