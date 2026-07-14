"""Validate session-produced scores, compute conviction, render report, update watchlist.

Usage:
    python -m research.score NVDA [--run-dir output/runs/YYYY-MM-DD]

Expects in the run dir:
    <TICKER>.json   — StockScores-shaped JSON + optional top-level "meta"
                      (graded by the Claude Code session)
    <TICKER>.md     — research notes with citations

Updates both files in place:
    <TICKER>.json   — adds top-level "conviction" (meta preserved)
    <TICKER>.md     — rewritten as the full report; original notes preserved
                      below config.NOTES_MARKER
and appends the idea to output/watchlist.json.

Re-running is safe/idempotent: conviction is stripped before re-validation and
notes are extracted from below the marker, so output is a fixed point.

Exits non-zero with readable validation errors so the session can fix the
JSON and retry.
"""

import argparse
import json
import math
import sys
from datetime import date

from pydantic import ValidationError

from . import config, tracking, watchlist
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


def render_report(
    scores: StockScores, notes: str, conviction: int, meta: dict,
    report_date: str | None = None,
) -> str:
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
**Date:** {report_date or date.today().isoformat()}

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

{config.NOTES_MARKER}
{notes}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a researched stock")
    parser.add_argument("ticker")
    parser.add_argument("--run-dir", default=None)
    parser.add_argument(
        "--backtest-date", default=None, metavar="YYYY-MM-DD",
        help="as-of scoring: record to the backtest tracking file, skip the watchlist",
    )
    args = parser.parse_args()

    from pathlib import Path

    if args.backtest_date:
        try:
            date.fromisoformat(args.backtest_date)
        except ValueError:
            sys.exit(f"invalid --backtest-date: {args.backtest_date}")

    if args.run_dir:
        run_dir = Path(args.run_dir)
    elif args.backtest_date:
        run_dir = config.backtest_dir(args.backtest_date)
    else:
        run_dir = config.RUNS_DIR / date.today().isoformat()
    ticker = args.ticker.upper()
    json_path = config.ticker_json_path(run_dir, ticker)
    md_path = config.ticker_md_path(run_dir, ticker)

    for p in (json_path, md_path):
        if not p.exists():
            sys.exit(f"missing input file: {p}")

    raw = json.loads(json_path.read_text())
    meta = raw.pop("meta", {})  # optional: company, thesis, source
    raw.pop("conviction", None)  # present on re-runs; recomputed below
    try:
        scores = StockScores(**raw)
    except ValidationError as e:
        sys.exit(f"scores JSON failed validation — fix and re-run:\n{e}")

    conviction = compute_conviction(scores)

    # On re-runs the md is already a report; the original notes live below the
    # marker. Fresh session-written notes have no marker — take the whole file.
    md_text = md_path.read_text()
    if config.NOTES_MARKER in md_text:
        notes = md_text.split(config.NOTES_MARKER, 1)[1]
    else:
        notes = md_text
    # normalize edge newlines so repeated runs are byte-identical
    notes = notes.strip("\n")

    report = render_report(scores, notes, conviction, meta, report_date=args.backtest_date)
    json_path.write_text(
        json.dumps({"conviction": conviction, "meta": meta, **scores.model_dump()}, indent=2)
    )
    md_path.write_text(report)
    if args.backtest_date:
        # backtests never touch the live watchlist or live tracking file
        tracking.record(
            ticker, conviction, scores.targets.current,
            research_date=args.backtest_date,
            path=config.backtest_tracking_path(args.backtest_date),
        )
        prefix = f"[backtest {args.backtest_date}] "
    else:
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
        tracking.record(ticker, conviction, scores.targets.current)
        prefix = ""
    print(f"{prefix}{ticker}: conviction {conviction}/100 — report at {run_dir / f'{ticker}.md'}")


if __name__ == "__main__":
    main()
