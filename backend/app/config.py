"""Paths and settings. Everything lives under the repo: workspace/, data/templates/."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(REPO_DIR / ".env")

WORKSPACE_DIR = Path(os.environ.get("BRIEF_WORKSPACE", REPO_DIR / "workspace"))
TEMPLATES_DIR = REPO_DIR / "data" / "templates"
VENDOR_DIR = REPO_DIR / "vendor"
SOLVERS_DIR = BACKEND_DIR / "solvers"
PLAYER_DIR = BACKEND_DIR / "player"
REFEREE_DIR = BACKEND_DIR / "referee"
DB_PATH = Path(os.environ.get("BRIEF_DB", WORKSPACE_DIR / "brief.db"))
# Arena results survive `make demo` wiping workspace/ so the demo leaderboard replays instantly
ARENA_CACHE_DIR = Path(os.environ.get("BRIEF_ARENA_CACHE", REPO_DIR / ".cache" / "arena"))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
INTAKE_MODEL = os.environ.get("BRIEF_INTAKE_MODEL", "claude-sonnet-5-5")
OFFLINE = os.environ.get("BRIEF_OFFLINE", "0") == "1" or not ANTHROPIC_API_KEY

# Arena limits (mirror Apex stage ceiling; fit the demo laptop)
SOLVER_CPUS = float(os.environ.get("BRIEF_SOLVER_CPUS", "2"))
SOLVER_MEM = os.environ.get("BRIEF_SOLVER_MEM", "2g")
SOLVER_TIMEOUT_S = int(os.environ.get("BRIEF_SOLVER_TIMEOUT_S", "600"))
TAKEOVER_MARGIN = float(os.environ.get("BRIEF_TAKEOVER_MARGIN", "0.01"))
MAX_UPLOAD_MB = 200
SPLIT_SEED = 42


def project_dir(project_id: str) -> Path:
    d = WORKSPACE_DIR / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d
