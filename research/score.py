"""Validate session-produced scores, compute conviction, render report, update watchlist.

Usage:
    python -m research.score NVDA [--run-dir output/runs/YYYY-MM-DD]

Expects in the run dir:
    <TICKER>.scores.json   — StockScores-shaped JSON (graded by the Claude Code session)
    <TICKER>.notes.md      — research notes with citations

Writes:
    <TICKER>.md            — final report
    <TICKER>.json          — validated scores + conviction
and appends the idea to output/watchlist.json.

Exits non-zero with readable validation errors so the session can fix the
scores JSON and retry.
"""

import argparse
import json
import math
import sys
from datetime import date

from pydantic import ValidationError

from . import config, watchlist
from .schemas import StockScores


def compute_conviction(scores: StockScores) -> int:
    """conviction = (growth*0.35 + moat*0.25 + catalysts*0.25) * 10 - bear_penalty,
    clamped to 0-100. Theoretical max is 85 with a zero bear penalty."""
    raw = (
        scores.growth.subscore * config.WEIGHTS["growth"]
        + scores.moat.subscore * config.WEIGHTS["moat"]
        + scores.catalysts.subscore * config.WEIGHTS["catalysts"]
    ) * 10
    raw -= scores.bear.penalty
    # round half-up (Python's round() is banker's rounding: round(48.5) == 48)
    return max(0, min(100, math.floor(raw + 0.5)))


def render_report(scores: StockScores, notes: str, conviction: int, meta: dict) -> str:
    g, m, c, b = scores.growth, scores.moat, scores.catalysts, scores.bear
    growth_rows = "\n".join(
        f"| {q.quarter} | {q.revenue_yoy_pct if q.revenue_yoy_pct is not None else 'n/a'} | {q.source} |"
        for q in g.quarters
    )
    breakdown = (
        f"| Criterion | Subscore | Weight | Points |\n"
        f"|---|---|---|---|\n"
        f"| Growth trend | {g.subscore}/10 | 35% | {g.subscore * 3.5:.1f} |\n"
        f"| Moat | {m.subscore}/10 | 25% | {m.subscore * 2.5:.1f} |\n"
        f"| Catalysts | {c.subscore}/10 | 25% | {c.subscore * 2.5:.1f} |\n"
        f"| Bear penalty | — | — | -{b.penalty} |\n"
    )
    catalyst_lines = "\n".join(
        f"- **{cat.classification.upper()}** ({cat.timeframe}): {cat.description} — {cat.rationale}"
        for cat in c.catalysts
    )
    bear_lines = "\n".join(
        f"- (severity {bc.severity}/10) {bc.description}\n  - Rebuttal: {bc.rebuttal}"
        for bc in b.bear_cases
    )
    t = scores.targets
    return f"""# {meta.get('company', scores.ticker)} ({scores.ticker}) — Conviction {conviction}/100

**Thesis:** {meta.get('thesis', 'n/a')}
**Source:** {meta.get('source', 'n/a')}
**Date:** {date.today().isoformat()}

**Verdict:** {scores.summary}

## Price Targets (12-month)

| Current | Bear | Base | Bull | Upside | Downside | Reward/Risk |
|---|---|---|---|---|---|---|
| {t.current:.2f} | {t.bear:.2f} | {t.base:.2f} | {t.bull:.2f} | {scores.upside_pct:+.1f}% | {scores.downside_pct:+.1f}% | {scores.reward_risk:.1f}x |

{t.rationale}

## Score Breakdown

{breakdown}
- Growth ({g.trend}): {g.rationale}
- Moat: {m.rationale}
- Catalysts: {c.rationale}
- Bear: {b.rationale}

## Revenue Growth (last 4 quarters)

| Quarter | YoY % | Source |
|---|---|---|
{growth_rows}

## Catalyst Classification

{catalyst_lines}

## Bear Cases

{bear_lines}

---

# Full Research Notes

{notes}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a researched stock")
    parser.add_argument("ticker")
    parser.add_argument(
        "--run-dir", default=str(config.RUNS_DIR / date.today().isoformat())
    )
    args = parser.parse_args()

    from pathlib import Path

    run_dir = Path(args.run_dir)
    ticker = args.ticker.upper()
    scores_path = run_dir / f"{ticker}.scores.json"
    notes_path = run_dir / f"{ticker}.notes.md"

    for p in (scores_path, notes_path):
        if not p.exists():
            sys.exit(f"missing input file: {p}")

    raw = json.loads(scores_path.read_text())
    meta = raw.pop("meta", {})  # optional: company, thesis, source
    try:
        scores = StockScores(**raw)
    except ValidationError as e:
        sys.exit(f"scores JSON failed validation — fix and re-run:\n{e}")

    conviction = compute_conviction(scores)
    notes = notes_path.read_text()

    (run_dir / f"{ticker}.md").write_text(
        render_report(scores, notes, conviction, meta)
    )
    (run_dir / f"{ticker}.json").write_text(
        json.dumps({"conviction": conviction, **scores.model_dump()}, indent=2)
    )
    watchlist.add(
        [
            {
                "ticker": ticker,
                "company": meta.get("company", ticker),
                "thesis": meta.get("thesis", scores.summary),
                "conviction": conviction,
                "current_price": scores.targets.current,
                "upside_pct": round(scores.upside_pct, 1),
                "downside_pct": round(scores.downside_pct, 1),
                "reward_risk": round(scores.reward_risk, 2),
            }
        ]
    )
    print(f"{ticker}: conviction {conviction}/100 — report at {run_dir / f'{ticker}.md'}")


if __name__ == "__main__":
    main()
