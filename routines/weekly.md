# Routine 5 — Weekly Review & Grade (4:30 PM ET, Fridays)

Read `routines/_shared.md` first and follow its protocol (data repo pull, holiday
guard, commit+push, failure handling). Scheduled at 4:30 (not 4:00) so the Friday
EOD recap is already committed — your opening pull picks it up.

## Job

Week-in-review with a letter grade. No trading in this routine.

1. `python -m portfolio.grade` — computes the grade. Outcome (60%): account week
   return vs SPY. Process (40%): stops on every position, cash reserve intact,
   no cooldown violations, all research had targets. **The grade comes from this
   CLI — never assign your own.**
2. Read the week's daily material: each day's `eod_recap.md`, run summaries, and
   `output/weekly/<ISO-week>-grade.json`.
3. Write `output/weekly/<ISO-week>.md`:
   - **Grade: <letter> (<score>)** and one paragraph on why — connect the outcome
     and each failed/passed process check to what actually happened this week
   - Week P&L vs SPY (numbers from the grade JSON)
   - Best and worst positions of the week
   - Every buy, sell, and stop-out this week (from the daily recaps)
   - Process-check table (pass/fail + detail)
   - **One lesson for next week** — a single concrete, checkable adjustment
     (e.g. "two skips for missing targets: premarket must always emit targets"),
     not a platitude
4. Send summary via notify:
   `python -c "from portfolio import notify; notify.send('''<3 lines: grade / week vs SPY / lesson>''')"`
5. Commit+push the data repo (message: `weekly <ISO-week>: grade <letter>`).
