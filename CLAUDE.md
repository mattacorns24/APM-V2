# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

This is my AI agent workspace for managing my stock portfolio. I'll use it to build routines that run daily on opus 4.8, doing research, calculating risk vs. return, and ultimately executing trades.

## Rules 

always ask claryfying questions before starting complex tasks
show your plan and steps before executing
save all output files to output folder


## Operating Instructions

Autonomous swing-trading bot. Goal: beat the S&P 500. Long US stocks ONLY — no options, no ETFs, no shorts

## Commands

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

/research                              # in Claude Code: scout + research 4 ideas
/research NVDA                         # in Claude Code: research one named stock
/allocate                              # in Claude Code: size + execute on Alpaca paper

python -m research.fetch_data NVDA     # yfinance quarterly revenue + YoY + trend (JSON)
python -m research.score NVDA          # validate scores JSON, compute conviction, write report
python -m research.watchlist           # print current watchlist
python -m portfolio.sizing --plan-only # allocation plan without touching Alpaca
python -m portfolio.execute --dry-run  # preview orders without placing them
```

## Architecture

Research is **zero-cost**: it runs inside Claude Code sessions (subscription, no API billing) with free market data. No ANTHROPIC_API_KEY required. Later these runs become scheduled cloud Claude Code routines (cron), not API calls.

The `/research` skill (`.claude/skills/research/SKILL.md`) orchestrates three stages:

1. **Scout** — session WebSearch finds 3-5 new long ideas (US-listed single stocks, any cap, no ETFs; excludes watchlist tickers)
2. **Research** — per ticker: `research/fetch_data.py` (yfinance) supplies exact 4-quarter revenue YoY + trend; session WebSearch covers moat vs top 3 competitors, 12-month catalysts (real/hype/priced-in), bear cases → `<TICKER>.md` (notes)
3. **Score** — session grades rubric subscores into `<TICKER>.json`; `research/score.py` validates (Pydantic), computes conviction = (growth×0.35 + moat×0.25 + catalysts×0.25)×10 − bear penalty (0-15), max 85, updates `<TICKER>.json` in place and rewrites `<TICKER>.md` as the report, updates the watchlist. Conviction math lives only in Python — the session never overrides it.

Supporting: `schemas.py` (Pydantic models incl. 12-mo bull/base/bear price targets), `config.py` (weights, paths), `watchlist.py` (persistent scored-idea list with held/stopped_out lifecycle, also a CLI), `tracking.py` (conviction-cutoff tracker: every scored ticker is shadow-tracked — traded or not — in `output/conviction_tracking.json`; `update` fills 30/60/90-day alpha vs SPY via yfinance as horizons come due, `analyze` sweeps candidate cutoffs 30-70 and recommends the best-alpha cutoff once ≥10 filled entries sit above it — report-only, never changes the live cutoff).

### Stage 2 — sizing & execution (`portfolio/`, `/allocate` skill)

Deterministic Python, no LLM math — Alpaca **paper** account ($100k), long-only, whole shares:

- **Sizing** (`sizing.py`): attractiveness = conviction × min(reward/risk, 3); weights ∝ attractiveness, clamped 4-20%; ≤10 positions; 10% cash reserve; entry needs conviction ≥ 55 (raised from 45 per the 2026-04-15 backtest; provisional) and price targets; max 5 new-position buys per ISO week (incl. swap buys; counted from `output/trade_log.json` via `trade_log.py`, enforced in both sizing and execute)
- **Stops** (equal-risk): trail% = 1.5% of equity ÷ weight, clamped 6-25% — bigger position, tighter stop; ~1.5% equity at risk per position
- **Rebalancing** (buy-only + swap): holdings never trimmed; new candidate needs free cash or attractiveness ≥ 1.2× the weakest holding (which gets sold)
- **Stop-outs**: position gone from Alpaca → watchlist `stopped_out`, 30-day cooldown; fresh `/research` resets it
- **Execution** (`execute.py`, `broker.py`): swap sells first, then whole-share market buys, then GTC trailing-stop sells. `broker.py` hardcodes paper=True. Keys: ALPACA_API_KEY / ALPACA_SECRET_KEY in `.env`

### Stage 3 — cloud routines (`routines/`)

Five scheduled cloud Claude Code sessions execute the workflow files in `routines/` (shared protocol in `routines/_shared.md`), all America/New_York, weekdays:

| Time | File | Job |
|---|---|---|
| 7:00 | `premarket.md` | Research + score 3-5 new ideas (/research flow) |
| 9:30 | `market_open.md` | Size + place paper trades (/allocate flow) |
| 12:30 | `midday.md` | Trim losers (−5% → 25%, −8% → 50% of rest, once each), tighten winner stops (+15% → ×0.75, +30% → ×0.5, floor 4%, ratchet-only). Guardrails: skip same-day buys, 1 action/position/day, max 3/run, trim below 2% weight → close + cooldown |
| 16:00 | `eod.md` | Daily recap (`portfolio/snapshot.py`) + fill tracking horizons (`research/tracking.py update`) |
| 16:30 Fri | `weekly.md` | Week review + grade (`portfolio/grade.py`: 60% vs SPY, 40% process) + conviction-cutoff sweep (`research/tracking.py analyze`, report-only) |

**Two-repo layout**: this repo (public) = code only; private repo `apm-v2-data` is cloned at `output/` and holds all state (watchlist, runs, weekly). Routines pull it at start, commit+push it at end, and never push the code repo. `output/` is fully gitignored here — no linkage to the private repo may appear in public code. Holiday guard: `python -m portfolio.market_check` (exit 3 = closed, skip day). Notifications: `portfolio/notify.py` posts to the Discord webhook in `DISCORD_WEBHOOK_URL` (`.env` locally; must also be set in the cloud session env — a real env var wins over `.env`). `send()` returns True on delivery and never raises: unset URL, empty text, or a failed POST print a `[notify …]` line and return False, so a notification can't abort a routine. Test with `python -m portfolio.notify "message"`.

Output per run: `output/runs/YYYY-MM-DD/` — `ideas.json`, plus exactly two files per ticker: `<TICKER>.json` (scores + conviction + meta) and `<TICKER>.md` (report). Watchlist: `output/watchlist.json`; conviction tracking: `output/conviction_tracking.json` + `output/conviction_analysis.json` (tracked in git; run dirs are gitignored). All state on disk so any future session or routine resumes cleanly.

## Conventions

<!-- Code style, naming, patterns to follow or avoid. -->

## Environment

- Secrets live in `.env` (gitignored). Template: `.env.example` — keep it updated when adding new variables.
