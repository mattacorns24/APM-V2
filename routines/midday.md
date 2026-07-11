# Routine 3 — Midday: Trim Losers, Tighten Winner Stops (12:30 PM ET, Mon–Fri)

Read `routines/_shared.md` first and follow its protocol (data repo pull, holiday
guard, commit+push, failure handling).

## Strategy (all math in Python — never adjust the numbers yourself)

- **Losers**: P&L ≤ −5% vs entry → sell 25% of the position; ≤ −8% → sell 50% of
  the remainder. Each step fires once per position, ever. The trailing stop stays
  on the rest as the final exit.
- **Winners**: gain ≥ +15% → trailing stop tightened to 0.75×; ≥ +30% → 0.5×.
  Floor 4%. Stops only ever tighten.
- **Guardrails**: positions bought this morning are exempt; one action per
  position per day; max 3 actions per run; a trim that would leave < 2% weight
  becomes a full close (starts the 30-day cooldown).

## Job

1. `python -m portfolio.snapshot` — closing state of the book.
2. `python -m portfolio.review` — plans the actions (writes `midday_review.json`).
3. `python -m portfolio.adjust` — executes them: cancel stop → sell/re-place →
   new stop. Exit code 2 means a stop re-placement failed and a position may be
   UNCOVERED — check `midday_execution.json`, attempt one manual
   `python -c "from portfolio import broker; broker.trailing_stop('<T>', <qty>, <trail>)"`
   with the values from the report, and flag it prominently in the summary.
4. Write `output/runs/<date>/midday_review.md`:
   - positions table (qty, entry, current, P&L%, weight, trail%)
   - actions executed with before/after (qty or trail)
   - skips with guardrail reasons
   - any warnings from the execution report, verbatim
5. Commit+push the data repo (message: `midday <date>: <n> trims, <m> tightens`).

## Invariants

- Never open a new position. Never loosen a stop. Never trade a ticker not
  already held. All quantities, trail percentages, and thresholds come from the
  CLIs.
