---
name: research
description: Run the APM-V2 stock research workflow — scout new long trade ideas via web search, deep-research each (growth, moat, catalysts, bear cases), grade against the conviction rubric, and produce scored reports plus watchlist updates. Use when asked to "research stocks", "find trade ideas", "run research", or "/research [TICKER]". With a ticker argument, researches that single stock and skips scouting.
---

# APM-V2 Research Workflow

You are running the research stage of an automated portfolio manager whose goal is to beat the S&P 500. Run **fully autonomously** — never ask the user questions mid-run; on hard failure for one ticker, write the error to the run directory and continue with the rest.

Python env: `.venv/bin/python` at the repo root (fall back to `python3` if missing).

## Setup

1. `RUN_DIR=output/runs/$(date +%F)` — create it.
2. `python -m research.watchlist` — note tracked tickers (scout must exclude them).

## Mode

- **`/research TICKER`** — skip scouting; research just that stock. Use `{"ticker": ..., "company": ..., "source": "manual", "thesis": "Manually requested research"}` as the idea.
- **`/research`** (no argument) — scout first, then research each idea. Default 4 ideas, never more than 5.

## Stage 1 — Scout (no-arg mode only)

Use WebSearch to scan current financial news, earnings coverage, and analyst commentary for fresh **long** ideas.

Universe rules (hard constraints):
- US-listed single stocks only (NYSE/NASDAQ, ADRs allowed), any market cap
- Long ideas only — no ETFs, no options, no shorts
- Exclude all watchlist tickers
- Prefer fresh angles: recent earnings surprises, guidance raises, product launches, insider buying, sector inflections, underfollowed names. Avoid consensus mega-cap darlings unless there is a genuinely new catalyst.

Write `$RUN_DIR/ideas.json`: array of `{"ticker", "company", "source", "thesis"}`.

## Stage 2 — Per ticker: data, research, notes

For each idea:

1. **Hard numbers first:** `python -m research.fetch_data TICKER` — exact quarterly revenue + YoY from yfinance. If any `revenue_yoy_pct` is `null`, find the missing prior-year revenue via WebSearch and compute it; label those quarters `"source": "web"`. If fetch_data errors entirely, source all four quarters from the web.
2. **Qualitative research** via WebSearch/WebFetch:
   - **Moat:** identify the top 3 competitors; assess positioning against each (share, pricing power, switching costs, technology, distribution).
   - **Catalysts (next 12 months):** each with expected timing, judged REAL (material and underappreciated), HYPE (narrative without fundamental support), or ALREADY PRICED IN (reflected in valuation) — justify with evidence.
   - **Bear cases:** strongest arguments against, each with severity and best rebuttal. Be genuinely adversarial — this section protects capital.
   - **Price targets (12-month):** estimate bull / base / bear price targets anchored to valuation evidence (multiples vs peers and history, growth trajectory, analyst ranges as sanity check). `current` must be the fetch_data price. Must satisfy bear < base <= bull. Explain the derivation.
3. Write `$RUN_DIR/TICKER.notes.md` — markdown sections: Growth Trend, Moat & Competitive Positioning, Catalysts (Next 12 Months), Bear Cases, Price Targets, Sources. Cite sources. If a number cannot be found, say so — never guess.

## Stage 3 — Grade and score

Grade subscores strictly from the notes and fetch_data numbers, per this rubric:

- **growth.subscore (0-10):** 9-10 = strong accelerating YoY growth; 5-6 = steady but flat; 0-2 = sharply decelerating or shrinking. Use the exact fetch_data YoY numbers.
- **moat.subscore (0-10):** 9-10 = dominant vs all top-3 competitors with durable advantages; 5-6 = holds its own, no clear edge; 0-2 = losing ground.
- **catalysts.subscore (0-10):** weight REAL heavily, HYPE near zero, PRICED IN slightly positive at best. 9-10 = multiple real, underappreciated catalysts inside 12 months.
- **bear.penalty (0-15):** 0-3 = bear cases weak or well-rebutted; 8-11 = at least one credible thesis-breaking risk; 12-15 = bear case stronger than the bull case.

Write `$RUN_DIR/TICKER.scores.json` matching `research/schemas.py::StockScores` exactly, plus an optional top-level `"meta"` object (`company`, `thesis`, `source`) for the report header:

```json
{
  "meta": {"company": "...", "thesis": "...", "source": "..."},
  "ticker": "XYZ",
  "targets": {"bull": 320.0, "base": 265.0, "bear": 180.0, "current": 211.0,
              "rationale": "how the targets were derived"},
  "growth": {"quarters": [{"quarter": "FQ ending 2026-04-30", "revenue_yoy_pct": 12.3, "source": "yfinance"}],
             "trend": "accelerating", "subscore": 8, "rationale": "..."},
  "moat": {"competitors": ["A", "B", "C"], "positioning": "...", "subscore": 7, "rationale": "..."},
  "catalysts": {"catalysts": [{"description": "...", "timeframe": "Q3 2026",
                "classification": "real", "rationale": "..."}], "subscore": 6, "rationale": "..."},
  "bear": {"bear_cases": [{"description": "...", "severity": 7, "rebuttal": "..."}],
           "penalty": 8, "rationale": "..."},
  "summary": "Two-sentence overall verdict."
}
```

Then run: `python -m research.score TICKER` — it validates the JSON, computes the conviction (weighted rubric: growth 35% / moat 25% / catalysts 25%, minus bear penalty; max 85), writes `TICKER.md` + `TICKER.json`, and updates the watchlist. If validation fails, fix the scores JSON per the error and re-run. **Never compute or override the conviction number yourself.**

## Finish

Report to the user: conviction-sorted table (ticker, conviction, one-line verdict), path to the run directory, and any tickers that failed with why.
