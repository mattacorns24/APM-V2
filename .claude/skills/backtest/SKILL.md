---
name: backtest
description: Backtest the conviction rubric against history — scout 10 mixed-quality ideas from a past date's news, score them strictly as-of that date, measure 30/60/90-day alpha vs SPY, and sweep conviction cutoffs to recommend one. Use when asked to "backtest", "backtest the conviction cutoff", or "/backtest [YYYY-MM-DD]". Date defaults to 90 days ago.
---

# APM-V2 Conviction-Cutoff Backtest

You are running a retrospective test of the conviction rubric. Pretend it is `$AS_OF` — everything you research, cite, and score must reflect only what was knowable then. Run **fully autonomously**; on hard failure for one ticker, write the error to the backtest dir and continue.

Python env: `.venv/bin/python` at the repo root (fall back to `python3`).

## Setup

1. `AS_OF` = the date argument, else 90 days ago (`date -v-90d +%F` on macOS).
2. `BT_DIR=output/backtest/$AS_OF` — create it.
3. `python -m research.watchlist` — note tracked tickers (excluded from scouting).

## Hindsight discipline (hard rules)

- Every qualitative claim must come from a source **published on or before $AS_OF**. Verify the dateline on the page (WebFetch if the search snippet is unclear). **Reject undated sources outright.**
- Search with month/year anchors: `"best stocks to buy <Month> <Year>"`, `"<Month> <Year> stock upgrades"`, `"Q<N> earnings beat" <Month> <Year>`, `"<ticker> stock" "<Month> <Year>"`. Prefer earnings coverage and analyst notes from the weeks before $AS_OF.
- Growth numbers come from `fetch_data --as-of` only — it already limits quarters to those reported by $AS_OF. **Never backfill later quarters from the web.**
- `targets.current` MUST equal the fetch_data as-of price (the $AS_OF close) — never today's price. Anchor price targets to multiples and analyst ranges as they stood then.
- Write moat/catalysts/bear cases **as known then**. Events after $AS_OF — even ones you know happened — are future possibilities, not facts.
- **Leak rule:** if a post-$AS_OF fact slips into any ticker's notes, or you could not fully avoid relying on one, do not silently rewrite history — list it under "Hindsight leaks" in the final report caveats.

## Stage 1 — Scout 10 mixed-quality ideas

Same universe rules as the research skill: US-listed single stocks (any cap, ADRs OK), long ideas only, no ETFs, exclude watchlist tickers.

**Deliberately mix quality** — the sweep needs conviction spread, so pick from what $AS_OF-era coverage said (not from known outcomes):
- ~4 **strong**: clear beats, guidance raises, real catalysts per coverage then
- ~3 **mid**: steady names, no obvious edge
- ~3 **weak**: hype-driven, decelerating, or carrying a heavy bear case in coverage then

Write `$BT_DIR/ideas.json`: array of `{"ticker", "company", "source", "thesis", "quality_bucket"}` (`strong|mid|weak`).

## Stage 2 — Research and score each ticker

Per ticker (mirror the research skill's per-ticker flow):

1. `python -m research.fetch_data TICKER --as-of $AS_OF`
2. Strict-dated qualitative research per the discipline rules: moat vs top 3 competitors, 12-month catalysts (real/hype/priced-in), bear cases, bull/base/bear price targets — all as of $AS_OF.
3. Write `$BT_DIR/TICKER.md` — same sections as the research skill, and the Sources section must list each source **with its publication date** (all ≤ $AS_OF).
4. Write `$BT_DIR/TICKER.json` — StockScores shape + top-level `"meta"`, graded with the standard rubric. **Never compute or override conviction yourself.**
5. `python -m research.score TICKER --run-dir $BT_DIR --backtest-date $AS_OF` — validates, adds conviction to the JSON, rewrites the md as the report. Backtest mode skips the live watchlist and records to `$BT_DIR/tracking.json`. If validation fails, fix `TICKER.json` and re-run.

## Stage 3 — Outcomes and cutoff sweep

1. `python -m research.tracking update --file $BT_DIR/tracking.json` — fills 30/60/90-day alpha vs SPY. If the 90-day horizon is due exactly today it only fills after the market close — re-run then, or note the gap.
2. `python -m research.tracking analyze --file $BT_DIR/tracking.json --min-sample 3` — writes `$BT_DIR/analysis.json`.

## Stage 4 — Report

Write `$BT_DIR/report.md`:

- **Per-ticker table**: ticker, quality bucket, conviction, 30/60/90-day alpha
- **Sweep tables** per horizon (from analysis.json) and the recommendation
- **Live-gate comparison**: which tickers conviction ≥ 45 (current `ENTRY_THRESHOLD`) would have admitted; avg alpha of admitted vs excluded
- **Caveats (mandatory)**: n=10; a single time window, so the result is regime-dependent and **provisional until live forward tracking (`output/conviction_tracking.json`) confirms it**; retrospective scouting bias (April coverage of names you may already know did well); any flagged hindsight leaks
- State explicitly: **report-only — `portfolio/config.py::ENTRY_THRESHOLD` was not changed**; the user updates it manually after review
- If convictions cluster within ~10 points, say the sweep is uninformative and why

## Finish

Report to the user: the recommended cutoff (or "no recommendation"), the per-ticker outcome table, path to `$BT_DIR/report.md`, and any tickers that failed with why.
