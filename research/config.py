"""Central configuration for the research workflow."""

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
