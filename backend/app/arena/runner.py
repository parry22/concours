"""Run solver submissions through the referee in Docker. Mirrors the Apex contract and limits.

Per submission: internal network -> player container (submission mounted read-only) -> referee container
(env MATCH_ID/SEED/CONFIG_JSON/PLAYER_URLS/NUM_PLAYERS, /data bind) -> result.json. One at a time.
"""
from __future__ import annotations

import json
import shutil
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

import docker
from docker.errors import DockerException, ImageNotFound, NotFound

from app.config import SOLVER_CPUS, SOLVER_MEM, SOLVER_TIMEOUT_S, SOLVERS_DIR, project_dir
from app.arena.stage import competition_dir

SOLVERS = ["baseline_logreg", "lgbm_default", "lgbm_tuned"]


@dataclass
class RunResult:
    ok: bool
    result: dict | None
    error: str | None
    seconds: float
    logs_dir: Path


def client() -> docker.DockerClient:
    return docker.from_env()


def image_tag(project_id: str, side: str) -> str:
    return f"brief-{side}-{project_id}"


def build_images(project_id: str, log) -> None:
    comp = competition_dir(project_id)
    cli = client()
    for side in ("player", "referee"):
        tag = image_tag(project_id, side)
        log(f"building {tag} from {comp}/{side}/Dockerfile")
        t0 = time.monotonic()
        _, stream = cli.images.build(path=str(comp), dockerfile=f"{side}/Dockerfile", tag=tag, rm=True)
        for chunk in stream:
            if "stream" in chunk and chunk["stream"].strip():
                log(chunk["stream"].rstrip())
        log(f"built {tag} in {time.monotonic() - t0:.0f}s")


def image_id(project_id: str, side: str) -> str | None:
    try:
        return client().images.get(image_tag(project_id, side)).id  # "sha256:..."
    except (ImageNotFound, DockerException):
        return None


def run_submission(project_id: str, submission_id: str, solver: str, config: dict, *, seed: int = 0, timeout_s: int = SOLVER_TIMEOUT_S,
                   submission_path: Path | None = None) -> RunResult:
    cli = client()
    logs_dir = project_dir(project_id) / "arena" / submission_id
    out_dir = logs_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir.chmod(0o777)
    sub_path = submission_path or (SOLVERS_DIR / solver / "submission.py")
    net_name = f"brief-net-{project_id}-{submission_id}"
    player_name = f"brief-player-{project_id}-{submission_id}"
    t0 = time.monotonic()
    net = player = referee = None
    try:
        net = cli.networks.create(net_name, driver="bridge", internal=True)
        player = cli.containers.run(
            image_tag(project_id, "player"),
            name=player_name,
            network=net_name,
            detach=True,
            nano_cpus=int(SOLVER_CPUS * 1e9),
            mem_limit=SOLVER_MEM,
            volumes={str(sub_path): {"bind": "/app/submission.py", "mode": "ro"}},
        )
        referee = cli.containers.run(
            image_tag(project_id, "referee"),
            network=net_name,
            detach=True,
            nano_cpus=int(1e9),
            mem_limit="1g",
            environment={
                "MATCH_ID": submission_id,
                "SEED": str(seed),
                "NUM_PLAYERS": "1",
                "PLAYER_URLS": f"http://{player_name}:8000",
                "CONFIG_JSON": json.dumps(config),
            },
            volumes={str(out_dir): {"bind": "/data", "mode": "rw"}},
        )
        exit_code = None
        deadline = time.monotonic() + timeout_s
        while exit_code is None:
            try:
                exit_code = referee.wait(timeout=5).get("StatusCode", 1)
                break
            except Exception:  # noqa: BLE001  (requests read timeout: referee still running)
                pass
            player.reload()
            if player.status in ("exited", "dead"):
                # the submission crashed at startup; do not wait for the referee's readiness timeout
                referee.kill()
                exit_code = -2
                tail = player.logs(tail=30).decode(errors="replace").strip()
                (logs_dir / "error.txt").write_text(f"player failed to start: {tail[-500:]}")
                break
            if time.monotonic() > deadline:
                referee.kill()
                exit_code = -1
                (logs_dir / "error.txt").write_text(f"timed out after {timeout_s}s")
                break
        (logs_dir / "referee.log").write_bytes(referee.logs())
        (logs_dir / "player.log").write_bytes(player.logs())
        result_path = out_dir / "result.json"
        if result_path.exists():
            result = json.loads(result_path.read_text())
            if "raw_scores" not in result:
                return RunResult(False, result, "result.json missing raw_scores", time.monotonic() - t0, logs_dir)
            return RunResult(True, result, None, time.monotonic() - t0, logs_dir)
        err = (logs_dir / "error.txt").read_text() if (logs_dir / "error.txt").exists() else f"referee exited {exit_code} without result.json"
        tail = referee.logs(tail=5).decode(errors="replace").strip()
        return RunResult(False, None, f"{err}: {tail[-400:]}", time.monotonic() - t0, logs_dir)
    except DockerException as e:
        (logs_dir / "error.txt").write_text(traceback.format_exc())
        return RunResult(False, None, f"docker error: {e}"[:500], time.monotonic() - t0, logs_dir)
    finally:
        for c in (referee, player):
            if c is not None:
                try:
                    c.remove(force=True)
                except (NotFound, DockerException):
                    pass
        if net is not None:
            try:
                net.remove()
            except (NotFound, DockerException):
                pass


def docker_available() -> tuple[bool, str]:
    try:
        v = client().version()
        return True, v.get("Version", "?")
    except DockerException as e:
        return False, str(e)
