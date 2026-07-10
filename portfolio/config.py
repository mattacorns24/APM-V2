"""Portfolio sizing, risk, and execution configuration."""

from research.config import OUTPUT_DIR, RUNS_DIR  # noqa: F401 (shared paths)

# Entry gate
ENTRY_THRESHOLD = 45          # minimum conviction to be a candidate

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

# Midday review — PLACEHOLDER thresholds, informational flags only.
# The trim/cut ruleset is not yet defined; nothing trades until this is True.
MIDDAY_RULES_ENABLED = False
FLAG_TRIM_GAIN_PCT = 25.0    # flag would_trim when unrealized gain >= this
FLAG_CUT_LOSS_PCT = -10.0    # flag would_cut when unrealized P&L <= this

# Weekly grade: outcome vs SPY (60%) + process discipline (40%)
GRADE_OUTCOME_WEIGHT = 0.6
GRADE_PROCESS_WEIGHT = 0.4
