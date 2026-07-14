# Routine 1 — Pre-Market Research (7:00 AM ET, Mon–Fri)

Read `routines/_shared.md` first and follow its protocol (data repo pull, holiday
guard, commit+push, failure handling).

## Job

Research and score 3–5 new trade ideas before the open. This is exactly the
`/research` skill flow (`.claude/skills/research/SKILL.md`) — follow it end to end:

1. `python -m research.watchlist` — note tracked tickers.
2. Scout via WebSearch: 3–5 fresh long ideas (US-listed single stocks, any cap,
   no ETFs), excluding all watchlist tickers. Write `output/runs/<date>/ideas.json`.
3. Per idea: `python -m research.fetch_data TICKER`, qualitative research
   (moat vs top 3, catalysts real/hype/priced-in, bear cases, 12-mo bull/base/bear
   price targets), write `TICKER.md` (research notes) and `TICKER.json`
   (scores + meta), then `python -m research.score TICKER` — it adds conviction
   to `TICKER.json` in place and rewrites `TICKER.md` as the full report.
4. Commit+push the data repo per shared protocol
   (message: `premarket <date>: researched <TICKERS>`).

## Handoff

The 9:30 market-open routine reads the updated watchlist. Your run dir must
contain, per ticker: `TICKER.json` (validated scores + conviction + meta) and
`TICKER.md` (full report), plus a watchlist entry with conviction
and targets. Finish with a one-paragraph summary in
`output/runs/<date>/premarket_summary.md` (ideas found, convictions, anything skipped).
