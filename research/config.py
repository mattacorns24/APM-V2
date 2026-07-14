"""Central configuration for the research workflow."""

import re
from pathlib import Path

# Conviction score rubric (user-approved):
#   conviction = (growth*0.35 + moat*0.25 + catalysts*0.25) * 10 - bear_penalty
# Subscores are 0-10, bear penalty 0-15. Theoretical max is 85 (bear-free);
# treat >=70 as high conviction, <40 as pass.
WEIGHTS = {
    "growth": 0.35,
    "moat": 0.25,
    "catalysts": 0.25,
}
BEAR_PENALTY_MAX = 15

# Scout settings
MAX_IDEAS = 5
DEFAULT_IDEAS = 4

# Paths (CLAUDE.md rule: all output files go to the output folder)
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
RUNS_DIR = OUTPUT_DIR / "runs"
WATCHLIST_PATH = OUTPUT_DIR / "watchlist.json"

# Conviction-cutoff tracking: every scored ticker is shadow-tracked (traded or
# not) so the cutoff sweep sees performance above AND below any candidate cutoff.
TRACKING_PATH = OUTPUT_DIR / "conviction_tracking.json"
ANALYSIS_PATH = OUTPUT_DIR / "conviction_analysis.json"
TRACK_HORIZONS = (30, 60, 90)  # calendar days after research date
BENCHMARK = "SPY"  # alpha benchmark (data only, never traded)
CUTOFF_SWEEP = range(30, 75, 5)  # candidate conviction cutoffs
MIN_CUTOFF_SAMPLE = 10  # filled entries above a cutoff before recommending

# Backtest (as-of) mode: separate namespace so the live tracking file and
# watchlist are never touched by retrospective runs.
BACKTEST_DIR = OUTPUT_DIR / "backtest"
REPORTING_LAG_DAYS = 40  # max gap between fiscal quarter end and its earnings report
BACKTEST_MIN_CUTOFF_SAMPLE = 3  # n=10 backtests can't meet MIN_CUTOFF_SAMPLE=10


def backtest_dir(as_of: str) -> Path:
    return BACKTEST_DIR / as_of


def backtest_tracking_path(as_of: str) -> Path:
    return backtest_dir(as_of) / "tracking.json"


# Per-ticker output contract: exactly two files per ticker in a run dir.
# <TICKER>.json — scores + meta, updated in place with conviction by score.py
# <TICKER>.md   — session notes, rewritten by score.py into the full report
# with the original notes preserved below NOTES_MARKER.
NOTES_MARKER = "<!-- APM:NOTES -->"

# Ticker files are the only uppercase-stem JSONs in a run dir (run-level files
# like ideas.json / allocation_plan.json are lowercase). Covers BRK.B, BF-B.
TICKER_STEM_RE = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")


def ticker_json_path(run_dir: Path, ticker: str) -> Path:
    return run_dir / f"{ticker}.json"


def ticker_md_path(run_dir: Path, ticker: str) -> Path:
    return run_dir / f"{ticker}.md"
