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
SPLIT_SEED = 42


def project_dir(project_id: str) -> Path:
    d = WORKSPACE_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d
