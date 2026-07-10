---
name: allocate
description: Size positions from the research watchlist and execute on the Alpaca paper account — conviction x reward/risk sizing, equal-risk trailing stops. Use when asked to "allocate", "size positions", "rebalance", "deploy the portfolio", or "/allocate". Pass "dry-run" to preview orders without placing them.
---

# APM-V2 Allocation & Execution

Deterministic stage — all math lives in Python; you only drive the CLIs and report. Run **fully autonomously**; never invent or adjust weights, share counts, or stop percentages.

Python env: `.venv/bin/python` at the repo root (fall back to `python3`).

## Steps

1. `python -m portfolio.sizing` — computes the allocation plan from the watchlist and live Alpaca paper account (`--plan-only` if the user asked for a plan without touching the account). Plan lands at `output/runs/<date>/allocation_plan.json`.
2. Show the user the printed plan table (buys with weight/dollars/trail%, sells, holds, skips with reasons).
3. `python -m portfolio.execute` — places the orders (market buys, then GTC trailing stops; swap sells first). Use `--dry-run` if the user said dry-run.
4. Report: what was bought/sold, each position's trailing stop %, stop-outs detected (cooldown started), skipped candidates and why, and cash remaining.

## Failure handling

- Missing Alpaca keys → tell the user to fill ALPACA_API_KEY / ALPACA_SECRET_KEY in `.env` (paper keys from app.alpaca.markets). Do not proceed.
- A skipped candidate with "no price targets" needs a fresh `/research TICKER` run — mention it, don't fix it here.
- Order failures are per-ticker: report and continue; never retry a failed order more than once.

## Invariants (do not violate)

- Paper account only — broker.py hardcodes paper=True; never change that.
- Long-only, whole shares, US-listed single stocks.
- Conviction/sizing/stop numbers come from the CLIs, never from your own judgment.
