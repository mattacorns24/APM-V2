# Routine 3 — Midday Review (12:30 PM ET, Mon–Fri) — REPORT ONLY

Read `routines/_shared.md` first and follow its protocol (data repo pull, holiday
guard, commit+push, failure handling).

## Status: trim/cut ruleset NOT YET DEFINED

This routine is a reporting shell. `MIDDAY_RULES_ENABLED = False` in
`portfolio/config.py`. **You must not place, modify, or cancel any order in this
routine, under any circumstances, even if a flag looks obvious.** When the user
defines the trim/tighten ruleset, the rules land in Python and this file gets
updated — not before.

## Job

1. `python -m portfolio.snapshot` — positions, P&L, stop coverage.
2. `python -m portfolio.review` — flags `would_trim` / `would_cut` candidates
   (placeholder thresholds, informational only).
3. Write `output/runs/<date>/midday_review.md`:
   - positions table (from the snapshot: qty, entry, current, P&L%, weight, trail%)
   - flagged candidates with the CLI's reasons
   - any position missing a trailing stop (highlight loudly)
   - closing line, verbatim: "No action taken — trim/cut ruleset not yet defined."
4. Commit+push the data repo (message: `midday <date>: <n> flags, no action`).
