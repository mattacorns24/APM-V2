"""Read-only midday position review.

Usage:
    python -m portfolio.review

Flags would_trim / would_cut candidates using placeholder thresholds in
config.py. MIDDAY_RULES_ENABLED is False: this module NEVER trades and the
flags are informational only, until the trim/cut ruleset is defined.

Writes output/runs/<date>/midday_review.json.
"""

import json
import sys
from datetime import date

from dotenv import load_dotenv

from . import config, snapshot


def review() -> dict:
    snap = snapshot.take()
    flags = []
    for p in snap["positions"]:
        pl = p["unrealized_pl_pct"]
        if pl >= config.FLAG_TRIM_GAIN_PCT:
            flags.append({"ticker": p["ticker"], "flag": "would_trim",
                          "reason": f"unrealized gain {pl:+.1f}% >= {config.FLAG_TRIM_GAIN_PCT}%"})
        elif pl <= config.FLAG_CUT_LOSS_PCT:
            flags.append({"ticker": p["ticker"], "flag": "would_cut",
                          "reason": f"unrealized P&L {pl:+.1f}% <= {config.FLAG_CUT_LOSS_PCT}%"})

    return {
        "rules_enabled": config.MIDDAY_RULES_ENABLED,
        "snapshot": snap,
        "flags": flags,
        "note": "No action taken — trim/cut ruleset not yet defined (MIDDAY_RULES_ENABLED=False).",
    }


def main() -> None:
    load_dotenv()
    try:
        result = review()
    except RuntimeError as e:
        sys.exit(str(e))

    run_dir = config.RUNS_DIR / date.today().isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "midday_review.json"
    path.write_text(json.dumps(result, indent=2))

    if result["flags"]:
        for f in result["flags"]:
            print(f"FLAG {f['flag']:<11} {f['ticker']:<6} {f['reason']}")
    else:
        print("no positions flagged")
    print(result["note"])
    print(f"review written to {path}")


if __name__ == "__main__":
    main()
