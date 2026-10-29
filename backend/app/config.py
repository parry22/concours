"""Paths and settings. Everything lives under the repo: workspace/, data/templates/."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(REPO_DIR / ".env")



def env(name: str, default: str) -> str:
    """`CONCOURS_<name>` first, then the older `BRIEF_<name>`, then the default."""
    return os.environ.get(f"CONCOURS_{name}", os.environ.get(f"BRIEF_{name}", default))


WORKSPACE_DIR = Path(env("WORKSPACE", str(REPO_DIR / "workspace")))
TEMPLATES_DIR = REPO_DIR / "data" / "templates"
VENDOR_DIR = REPO_DIR / "vendor"
SOLVERS_DIR = BACKEND_DIR / "solvers"
PLAYER_DIR = BACKEND_DIR / "player"
REFEREE_DIR = BACKEND_DIR / "referee"
DB_PATH = Path(env("DB", str(WORKSPACE_DIR / "concours.db")))
# Arena results survive `make demo` wiping workspace/ so the demo leaderboard replays instantly
ARENA_CACHE_DIR = Path(env("ARENA_CACHE", str(REPO_DIR / ".cache" / "arena")))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
INTAKE_MODEL = env("INTAKE_MODEL", "claude-sonnet-5-5")
# CONCOURS_OFFLINE=1 forces cached/default replies. Without it, Concours uses the API key if set, else the Claude Code
# CLI (the user's subscription), else cached/default replies.
OFFLINE_FORCED = env("OFFLINE", "0") == "1"
_HAS_CLI = bool(shutil.which("claude") or os.path.exists(os.path.expanduser("~/.local/bin/claude")))
OFFLINE = OFFLINE_FORCED or not (ANTHROPIC_API_KEY or _HAS_CLI)

# Arena limits (mirror Apex stage ceiling; fit the demo laptop)
SOLVER_CPUS = float(env("SOLVER_CPUS", "2"))
SOLVER_MEM = env("SOLVER_MEM", "2g")
SOLVER_TIMEOUT_S = int(env("SOLVER_TIMEOUT_S", "600"))
TAKEOVER_MARGIN = float(env("TAKEOVER_MARGIN", "0.01"))
# Model versions: a new version needs this relative gain on the private holdout (per project, this is the default)
DEFAULT_MIN_IMPROVEMENT = float(env("MIN_IMPROVEMENT", "0.01"))
# Performance watch: a relative drop over this on fresh labeled rows marks the project as slipping
DEFAULT_DRIFT_THRESHOLD = float(env("DRIFT_THRESHOLD", "0.10"))
# The solvers that build version 1 right after Protect
BASELINE_SOLVERS = ("baseline_logreg", "lgbm_default")
MAX_UPLOAD_MB = 200

# Apex filing: the private competition repo (owner/name on GitHub) and who to contact. The generator writes them into
# spec.yaml (image refs, cosign identity), HANDOFF.md and ONBOARDING_ISSUE.md; unset leaves TODO placeholders.
GITHUB_REPO = env("GITHUB_REPO", "").strip()
OWNER_NAME = env("OWNER_NAME", "").strip()
OWNER_EMAIL = env("OWNER_EMAIL", "").strip()
SPLIT_SEED = 42

# Browsers allowed to call the API from another origin (dev: the Next.js port). Production is same-origin.
ALLOWED_ORIGINS = [o.strip() for o in env("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]

# One niche: payment fraud. The other templates and the generic engine stay in the code, hidden behind this flag.
ENABLED_TEMPLATES = [t.strip() for t in env("ENABLED_TEMPLATES", "fraud").split(",") if t.strip()]

# Fraud defaults: the three intake questions, the simulated label delay, the evaluation windows
FRAUD_DEFAULTS = {
    "daily_capacity": 200,
    "review_cost": 10.0,
    "fraud_fee": 0.0,
    "label_delay_days": 30,
}
LABEL_DELAY_RANGE = (7, 60)  # simulated label_time = transaction_time + U(7, 60) days when the data has none
HOLDOUT_DAYS = 14
MIN_WINDOW_ROWS = 200
# Exploration: this share of the daily queue is random payments from outside the model's picks (at least 1 when the
# queue holds 20 or more), so analyst verdicts also reveal what the model misses. 0 turns it off.
EXPLORE_SHARE = float(env("EXPLORE_SHARE", "0.05"))  # a public check or private test window with fewer payments is refused at Protect
LEADERBOARD_DAYS = 7
SAMPLE_AS_OF_DAY = 154  # the sample's "today": day 154 of 183, so four later weeks exist for the drift demo
# Promotion gates
GATE_RESAMPLES = 1000
GATE_WIN_SHARE = 0.95
GATE_SEGMENT_DROP = 0.05
GATE_SECONDS_PER_10K = 5.0
AMOUNT_BANDS = (50.0, 500.0)  # under 50, 50 to 500, over 500
# Drift
HEALTH_DROP = 0.15
PSI_LIMIT = 0.2


def project_dir(project_id: str) -> Path:
    d = WORKSPACE_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d
