# Routine 4 — End-of-Day Recap (4:00 PM ET, Mon–Fri)

Read `routines/_shared.md` first and follow its protocol (data repo pull, holiday
guard, commit+push, failure handling).

## Job

Brief recap of the day's operations. No trading in this routine.

1. `python -m portfolio.snapshot` — closing state.
2. Read today's run dir (`output/runs/<date>/`): premarket summary, market-open
   summary, midday review, execution/skip logs.
3. Write `output/runs/<date>/eod_recap.md` — brief, human-readable:
   - **Day P&L**: $ and % (from the snapshot), equity and cash
   - **Actions today**: researched tickers + convictions, buys/sells with fills,
     stop-outs detected (cooldown started)
   - **Positions**: table with P&L and trailing stop per name; call out any
     missing stop
   - **Tomorrow's setup**: cooldowns ending soon, watchlist candidates that were
     skipped and why (e.g. "portfolio full", "no targets")
   - Keep it under ~40 lines. Recap, not analysis.
4. Send the 3-line summary via notify:
   `python -c "from portfolio import notify; notify.send('''<3 lines: day P&L / actions count / notable>''')"`
   (no-ops until the Discord webhook is configured — expected for now).
5. Commit+push the data repo (message: `eod <date>: <day P&L>`).
