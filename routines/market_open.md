# Routine 2 — Market Open Execution (9:30 AM ET, Mon–Fri)

Read `routines/_shared.md` first and follow its protocol (data repo pull, holiday
guard, commit+push, failure handling).

## Job

Deploy this morning's research into paper positions. This is exactly the
`/allocate` skill flow (`.claude/skills/allocate/SKILL.md`):

1. `python -m portfolio.sizing` — allocation plan from watchlist + live paper account.
2. Sanity-read the printed plan. Invariants that must hold (abort and write a
   FAILED file if any is violated): paper account, long only, buys are whole
   shares, weights ≤ 20%, every buy has a trail_pct.
3. `python -m portfolio.execute` — swap sells first, market buys, then GTC
   trailing stops. (Prefer running ~5 minutes after the open so opening auction
   volatility settles; the schedule already fires at 9:30 — do not add your own delay loop beyond order fills.)
4. Write `output/runs/<date>/market_open_summary.md`: fills (ticker, qty, avg
   price, weight, trail %), sells, skips with reasons, cash remaining.
5. Commit+push the data repo (message: `market_open <date>: <n> buys, <m> sells`).

## Rules

- Never adjust weights, share counts, or stop percentages yourself.
- If the plan has zero buys and zero sells, that is a valid outcome — write the
  summary saying so and finish.
