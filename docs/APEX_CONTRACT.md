# Apex competition contract (as verified, 2026-10-28)

Source of truth: `macrocosm-os/apex-competitions-builder` @ `49eb05e22a142ef2fe077545cc3e47ee3d9e86be` (2026-10-19) and the worked example `macrocosm-os/apex-competition-hello-world` @ `9b2ff70`. Where the product brief assumed something different, the difference is called out in **Concours vs Apex** boxes. This document is what `apex_builder/` generates against. Do not hand-write the spec from memory; `apex-dev preflight` is the judge.

## 1. What a competition package contains

A competition is its own repository holding:

| Item | Path (convention) | Notes |
|---|---|---|
| Spec | `spec.yaml` | `schema: apex.competition.v1`, JSON Schema at `src/apex_sdk/schema/apex.competition.v1.json`, `additionalProperties: false` at the root |
| Input schema + fixture | `input.schema.json`, `fixtures/input.json` | `input_schema` may be inline or `{ "$ref": "./input.schema.json" }`, resolved relative to the spec |
| Player image | `player/Dockerfile`, `player/launch.py`, `player/gym_v1/` | The miner submission server. `FROM python:3.12-slim`, uid 1000, `/app` + `/data`. Vendored `gym_v1`, never `FROM apex-player-base` |
| Referee image | `referee/Dockerfile`, `referee/referee.py`, `referee/gym_v1/` | Holds all ground truth and scoring. Runs `/app/referee.py` by convention; the spec has no referee command field |
| Baseline submission | `player/submission.py` | The `code` artifact miners fork. Must score above 0 through the full loop |
| Release workflow | `.github/workflows/release.yml` | On tag `v*`: build both images, push to GHCR, read digests, `cosign sign --yes` keyless. Spec digests must then be updated |
| Onboarding manifest | `HANDOFF.md` | Toolkit template at `skills/apex-competition-builder/HANDOFF.md`; pasted into the onboarding issue |
| Miner README | `README.md` | Task, metric, submission format. Must not describe anti-exploit defenses |

Onboarding is manual: the owner opens the GitHub issue template `.github/ISSUE_TEMPLATE/competition-onboarding.yml` on the toolkit repo; a Macrocosmos maintainer copies `spec.yaml` into the private `apex-competitions-registry`, activates on stage, then prod. Concours generates the issue body but never opens it.

## 2. `spec.yaml` fields

Required at root: `schema`, `id`, `version`, `display_name`, `kind`, `process_type`, `resources`, `submission`, `input_schema`, `defaults`. For `kind: solo` (what Concours emits) also `image`, `entrypoints`, `referee`, `signature`; `duel` and `external_evaluator` are forbidden.

| Field | Constraint |
|---|---|
| `schema` | `"apex.competition.v1"` |
| `id` | `^[a-z][a-z0-9_]{1,63}$`; `(id, version)` immutable once synced |
| `version` | semver `^[0-9]+\.[0-9]+\.[0-9]+$` |
| `display_name` | 1..128 chars |
| `kind` | `solo` |
| `process_type` | `cpu` |
| `resources` | `cpu_limit` (number > 0), `mem_limit` (`^[0-9]+(\.[0-9]+)?(Mi|Gi)$`, floor 256Mi), `gpu_count` (0). Ceilings: stage 2 CPU / 2Gi, prod 4 CPU / 4Gi |
| `image` | player image: `ref` (no tag, `^[a-z0-9.-]+(:[0-9]+)?/[a-z0-9._/-]+$`) + `digest` (`^sha256:[a-f0-9]{64}$`) |
| `submission` | `artifact_type` (`code` for Concours), `max_size_mb` (≤ 2048), `target_path` (absolute, `/app/submission.py`) |
| `screening` | optional; Concours sets `max_size_mb` and `extra_forbidden_modules: [socket, subprocess]` |
| `input_schema` | inline or `$ref` |
| `defaults` | `baseline_score`, `baseline_raw_score`, `round_length_in_days` (> 0), `submission_reveal_days` (≥ 0, norm 1, max 7), `lower_is_better` |
| `entrypoints.evaluate` | `command` (argv, no shell), `network_disabled` (false so the referee can reach the player), `allow_internet` (false; egress is blocked regardless), `timeout_s` (1..7200), `http_api { port, readiness_path, protocol: gym_v1 }` |
| `referee` | `protocol: gym_v1`, `image { ref, digest }`, `timeout_s` (1..7200) |
| `signature` | `cosign_identity` (workflow URL), `cosign_issuer` (`https://token.actions.githubusercontent.com`) |
| `solo` | optional `{ player_sandboxes: int ≥ 1 }` |

Hello-world `spec.yaml` is the template Concours fills (see `backend/app/apex_builder/templates/spec.yaml.j2`).

**Concours vs Apex: "private competition".** There is no spec field for privacy. Privacy is: private repo and images (the platform can pull private packages), the registry is always private, results stay hidden while a round is active, and submission code is revealed to other miners after `submission_reveal_days`. Concours sets `submission_reveal_days: 7` and states the terms in `HANDOFF.md`.

## 3. How the referee drives the player (gym_v1)

Transport is HTTP on a per-job network. The referee is the client, the player is the server. No shared volume, no stdin. Sandboxes have no internet, ever.

```
GET  /health                                        -> {"ready": bool}
POST /reset  {match_id, player_index, seed, config} -> 204
POST /act    {observation, deadline_ms}             -> {"action": ...}
```

`observation` and `action` are opaque JSON, competition-defined. The platform polls `readiness_path` before the referee starts (`Referee.readiness_timeout_s = 60`, poll 0.5 s). Client timeouts: `/reset` 30 s, `/act` `deadline_ms/1000 + 1` s.

Referee env injected by the platform:

```
MATCH_ID     opaque string, unique per (job, game_index)
SEED         int
CONFIG_JSON  opaque competition config (round input); `{}` if absent
PLAYER_URLS  comma-separated player base URLs
NUM_PLAYERS  int (defaults to len(PLAYER_URLS))
```

Kill timers: `evaluate.timeout_s` (player lifetime incl. startup) and `referee.timeout_s`. Killed without grace at the limit. Norm: median eval 1 to 10 minutes, 20 minutes hard ceiling.

**Concours vs Apex: player interface.** The brief assumed `fit(train)` / `predict(features)`. Apex players are gym_v1 HTTP servers. Concours keeps solver logic in a plain class (`fit`, `predict_proba`) and wraps it once in `player/launch.py`: `reset` trains on the public train split baked into the player image, `act` scores a batch `{"columns": [...], "rows": [[...]]}` and returns `{"scores": [...]}`.

**Concours vs Apex: data.** The schema has no data mount and no train/public/private concept. Hidden data must be baked into the referee image. The player receives no training data from the platform, so public train data is baked into the player image (treated as exposable, which is fine: the train split is public by design). The referee image holds `leaderboard.csv`, `holdout.csv` and both label files.

Known upstream bug (unmerged PR #22): `gym_v1/player.py do_POST` does not catch exceptions from `reset`/`act`, so a crashing submission drops the connection and the failure is charged to the referee. Concours's vendored copy (`vendor/gym_v1/player.py`) wraps dispatch and returns HTTP 500 with the error text.

## 4. Where results are written

`Referee.run()` writes `/data/result.json` as `json.dumps(asdict(GameResult))`:

```json
{"raw_scores": [0.84], "winner": 0, "terminal_reason": "scored", "steps": 2, "metadata": {}}
```

Solo: the platform reads `raw_scores[0]`. Direction comes from `defaults.lower_is_better`. There is no normalizer in the referee; the platform derives `score` from `raw_scores` against `baseline_raw_score`. Takeover rule: a submission must beat `max(baseline, current_top) * 1.01` (`SCORE_THRESHOLD = 0.01` in `macrocosm-os/apex`). Winner takes all emissions.

**Concours vs Apex: result shape.** The brief assumed `raw_score` plus `breakdown`. Correct shape is `raw_scores` (list) and free-form `metadata`. Concours writes `raw_scores: [private_holdout_primary_metric]` and `metadata: {public_score, private_score, primary_metric, secondary: {...}, breakdown: {...}, eval_time_in_seconds}`.

Failure semantics: referee crash or missing `result.json` scores 0 for all participants and is attributed to the referee, so never write a zeroed result to cover a referee bug. Player HTTP errors raise `PlayerError`; the referee decides the score (Concours: 0 with `terminal_reason: "player_error"`).

Optional: `/data/trace.jsonl` via `self.trace(event)`, `/data/history/` one file per task.

## 5. Local validation

Install the toolkit from git (PyPI `apex-competition-sdk` returns 404): `apex-competition-sdk @ git+https://github.com/macrocosm-os/apex-competitions-builder@49eb05e`. Entry point `apex-dev`.

| Command | What it does | Status |
|---|---|---|
| `apex-dev preflight --spec ./spec.yaml --input fixtures/input.json --env stage` | Draft 2020-12 schema validation, `$ref` resolution, env ceilings, fixture vs `input_schema`. No Docker | Works, exit 2 on failure |
| `apex-dev screen --repo .` | Flags missing `spec.yaml`/`HANDOFF.md`, all-zero or invalid digests, a "perfect baseline" (`baseline_score >= 1.0`), empty or identical `tasks` in the fixture | Works, exit 1 on findings |
| `apex-dev run ...` | Referee-driven local run | **Not implemented upstream. Prints the plan and exits 3** |

**Concours vs Apex: validation.** Because `apex-dev run` is unimplemented, Concours's "Validate with Apex toolkit" badge means all three of: `preflight` pass, `screen` pass, and a local two-container run by Concours's arena that follows the contract above and produced a valid `result.json`. The UI says exactly that.

Verified manual two-container loop (reproduced on this machine, 2026-10-28, `raw_scores: [1.0]`):

```bash
docker build -f player/Dockerfile  -t hello-world-player  .
docker build -f referee/Dockerfile -t hello-world-referee .
docker network create --internal hello-net
docker run -d --name hello-player --network hello-net --cpus 1 --memory 512m \
  -v "$PWD/player/submission.py:/app/submission.py:ro" hello-world-player
docker run --rm --network hello-net \
  -e MATCH_ID=local -e SEED=0 -e NUM_PLAYERS=1 \
  -e PLAYER_URLS='http://hello-player:8000' \
  -e CONFIG_JSON="$(cat fixtures/input.json)" \
  -v "$PWD/out:/data" hello-world-referee
cat out/result.json
docker rm -f hello-player && docker network rm hello-net
```

Gotchas found:
- Docker Desktop on macOS: bind-mounting a file from `/private/tmp` produced an empty directory inside the container (`IsADirectoryError: /app/submission.py`). Mount only from paths under `/Users`. Concours's `workspace/` is under the repo, so this holds.
- Use `--internal` networks; the README's plain bridge network has internet access, the platform does not.
- Local builds are `linux/arm64`; the release workflow builds amd64. Local image IDs are used as placeholder digests so `screen` passes; `release.yml` rewrites them after the GHCR push.
- `/usr/bin/python3` on this Mac is the Xcode shim and fails on the license prompt. Use `uv` / `python3.11`.

## 6. Resource and network rules Concours applies locally

Mirrors the stage ceiling and fits the demo laptop (Docker VM 4 CPUs, 4.8 GB): one solver at a time, `--cpus 2 --memory 2g`, 10-minute timeout, internal network with only the referee reachable, player uid 1000, submission mounted read-only at `/app/submission.py`.
