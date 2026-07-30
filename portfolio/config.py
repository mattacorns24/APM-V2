"""Portfolio sizing, risk, and execution configuration."""

from research.config import OUTPUT_DIR, RUNS_DIR  # noqa: F401 (shared paths)

# Entry gate
# 55 per 2026-04-15 backtest (output/backtest/2026-04-15/report.md): the 45-54
# band underperformed; provisional until live tracking confirms (~20 entries)
ENTRY_THRESHOLD = 55          # minimum conviction to be a candidate

# Weekly trade cap: at most this many new-position buys (including swap-funded
# buys) per ISO week (Monday reset). Counted from output/trade_log.json.
MAX_NEW_TRADES_PER_WEEK = 5

# Sizing: attractiveness = conviction * min(reward_risk, ATTRACT_RR_CAP);
# weights proportional to attractiveness, clamped below.
ATTRACT_RR_CAP = 3.0
MAX_POSITIONS = 10
MAX_WEIGHT = 0.20
MIN_WEIGHT = 0.04
MIN_CASH = 0.10               # equity fraction always kept in cash

# Equal-risk trailing stops: each position risks the same slice of equity.
#   trail_pct = RISK_BUDGET / weight, clamped to TRAIL_CLAMP (percent).
# 20% position -> 7.5% trail; 5% position -> 25% trail (clamped).
RISK_BUDGET = 0.015
TRAIL_CLAMP = (6.0, 25.0)

# Rebalancing: buy-only + swap. A new candidate displaces the weakest holding
# only if its attractiveness beats the holding's by this margin.
SWAP_MARGIN = 1.2

# Stop-outs: ticker ineligible for re-entry for this many days after its
# trailing stop fires. Fresh /research resets the clock immediately.
COOLDOWN_DAYS = 30

# Midday strategy: trim losers, tighten winner stops (user-approved ruleset).
MIDDAY_RULES_ENABLED = True
# Loser ladder: (P&L% vs avg entry, fraction of current qty to sell).
# Each step fires once per position, ever. Trailing stop stays = final exit.
LOSER_TRIM_STEPS = [(-5.0, 0.25), (-8.0, 0.50)]
# Winner ratchet: (gain% threshold, multiplier applied to current trail).
# Ratchet-only — a stop never loosens. Highest crossed step wins.
WINNER_TIGHTEN_STEPS = [(15.0, 0.75), (30.0, 0.50)]
TRAIL_FLOOR = 4.0            # trail % never tightens below this
MAX_MIDDAY_ACTIONS = 3       # per run, worst offenders first
DUST_WEIGHT = 0.02           # trim leaving < this weight -> close entirely (cooldown)

# Weekly grade: outcome vs SPY (60%) + process discipline (40%)
GRADE_OUTCOME_WEIGHT = 0.6
GRADE_PROCESS_WEIGHT = 0.4
