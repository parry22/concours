#!/usr/bin/env bash
# Apex-compatible local run: the exact signed images from GHCR, run on this machine through the same
# referee/player contract Apex uses, for several submissions, then fed into the project as attempts.
#
#   scripts/apex_local_run.sh verify   [--repo DIR]            cosign-verify both images (needs network)
#   scripts/apex_local_run.sh pull     [--repo DIR]            docker pull both images by digest (needs network)
#   scripts/apex_local_run.sh run      [--project PID] [--solvers a,b] [--fresh]   run the referee (works offline)
#   scripts/apex_local_run.sh import   [--project PID] [--solvers a,b]             feed result.json files into the app
#   scripts/apex_local_run.sh all      (verify, pull, run, import)
#
# Defaults: repo /Users/parry/concours-fraud-repo (the private competition repo, spec.yaml holds the digests),
# project 6974713c0ea7, solvers baseline_logreg,lgbm_default,lgbm_tuned,lgbm_velocity.
# Honesty: this is NOT a live network run. The app labels these attempts "Apex-compatible local run".
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CMD="${1:-}"; shift || true
REPO="${APEX_REPO:-/Users/parry/concours-fraud-repo}"
PID="${APEX_PROJECT:-6974713c0ea7}"
SOLVERS="baseline_logreg,lgbm_default,lgbm_tuned,lgbm_velocity"
FRESH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --project) PID="$2"; shift 2 ;;
    --solvers) SOLVERS="$2"; shift 2 ;;
    --fresh) FRESH=1; shift ;;
    *) echo "unknown argument $1" >&2; exit 2 ;;
  esac
done
COSIGN="${COSIGN:-$(command -v cosign || echo "$HOME/.local/bin/cosign")}"
SPEC="$REPO/spec.yaml"
[ -f "$SPEC" ] || { echo "no spec.yaml at $SPEC (set --repo)" >&2; exit 2; }
PLAYER_REF=$(grep -A2 '^image:' "$SPEC" | grep -oE 'ghcr.io/[a-z0-9._/-]+')
PLAYER_DIGEST=$(grep -A2 '^image:' "$SPEC" | grep -oE 'sha256:[0-9a-f]{64}')
REFEREE_REF=$(grep -A2 '^  image:' "$SPEC" | grep -oE 'ghcr.io/[a-z0-9._/-]+')
REFEREE_DIGEST=$(grep -A2 '^  image:' "$SPEC" | grep -oE 'sha256:[0-9a-f]{64}')
IDENTITY=$(grep -oE 'cosign_identity: .*' "$SPEC" | cut -d' ' -f2)
ISSUER=$(grep -oE 'cosign_issuer: .*' "$SPEC" | cut -d' ' -f2)
PLAYER="$PLAYER_REF@$PLAYER_DIGEST"; REFEREE="$REFEREE_REF@$REFEREE_DIGEST"
BASE="$ROOT/workspace/$PID/apex_local"
mkdir -p "$BASE"
VERIFIED="$BASE/verified.json"
HARDEN=(--cap-drop ALL --security-opt no-new-privileges:true --read-only --tmpfs /tmp:rw,noexec,nosuid,size=512m)
say() { echo "[apex-local] $*"; }

verify() {
  [ -x "$COSIGN" ] || { echo "cosign not found; install it (sigstore/cosign releases) or set COSIGN=" >&2; exit 2; }
  for img in "$PLAYER" "$REFEREE"; do
    say "cosign verify $img"
    "$COSIGN" verify --certificate-identity-regexp "^${IDENTITY//./\\.}@" --certificate-oidc-issuer "$ISSUER" "$img" >/dev/null 2>"$BASE/cosign.err" \
      || { echo "SIGNATURE VERIFICATION FAILED for $img" >&2; cat "$BASE/cosign.err" >&2; exit 1; }
  done
  printf '{"player": "%s", "referee": "%s", "identity": "%s", "issuer": "%s", "verified_at": "%s"}\n' \
    "$PLAYER" "$REFEREE" "$IDENTITY" "$ISSUER" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$VERIFIED"
  say "both signatures verified; recorded in $VERIFIED"
}

pull() {
  for img in "$PLAYER" "$REFEREE"; do
    docker manifest inspect "$img" >/dev/null 2>&1 || { echo "cannot read $img: run 'docker login ghcr.io' with a read:packages token" >&2; exit 2; }
    say "docker pull $img"; docker pull -q "$img"
  done
  say "images present: $(docker images --format '{{.Repository}}@{{.Digest}}' | grep -c concours-fraud) concours-fraud images"
}

check_local() {
  # offline: the images must be present with the pinned digests and have been verified since they were pulled
  for img in "$PLAYER" "$REFEREE"; do
    docker image inspect "$img" >/dev/null 2>&1 || { echo "image $img is not on this machine: run 'pull' with network" >&2; exit 2; }
  done
  [ -f "$VERIFIED" ] || { echo "no $VERIFIED: run 'verify' with network before the first run" >&2; exit 2; }
  grep -q "$PLAYER_DIGEST" "$VERIFIED" && grep -q "$REFEREE_DIGEST" "$VERIFIED" || { echo "$VERIFIED does not match the digests in spec.yaml: run 'verify' again" >&2; exit 2; }
  say "images present and verified (player $PLAYER_DIGEST, referee $REFEREE_DIGEST)"
}

run_one() {
  local solver="$1" dir="$BASE/$1" sub net player t0 code
  if [ "$solver" = "baseline_logreg" ] && [ -f "$REPO/player/submission.py" ]; then sub="$REPO/player/submission.py"; else sub="$ROOT/backend/solvers/$solver/submission.py"; fi
  [ -f "$sub" ] || { echo "no submission for $solver" >&2; return 1; }
  if [ -f "$dir/out/result.json" ] && [ "$FRESH" != 1 ]; then say "$solver: result.json already present (use --fresh to rerun)"; return 0; fi
  rm -rf "$dir"; mkdir -p "$dir/out"; chmod 777 "$dir/out"; cp "$sub" "$dir/submission.py"
  net="apex-local-net-$PID-$solver"; player="apex-local-player-$PID-$solver"
  docker network rm "$net" >/dev/null 2>&1 || true; docker rm -f "$player" >/dev/null 2>&1 || true
  docker network create --internal "$net" >/dev/null
  t0=$(date +%s)
  docker run -d --name "$player" --network "$net" --cpus 2 --memory 2g --pids-limit 256 "${HARDEN[@]}" \
    -v "$dir/submission.py:/app/submission.py:ro" "$PLAYER" >/dev/null
  say "$solver: player started ($(docker image inspect --format '{{.Architecture}}' "$PLAYER") image, emulated on $(uname -m) if different); referee running"
  set +e
  docker run --rm --network "$net" --cpus 1 --memory 1g --pids-limit 128 "${HARDEN[@]}" \
    -e MATCH_ID="apex-local-$solver" -e SEED=0 -e NUM_PLAYERS=1 -e PLAYER_URLS="http://$player:8000" \
    -e CONFIG_JSON="$(cat "$REPO/fixtures/input.json")" -v "$dir/out:/data" "$REFEREE" > "$dir/referee.log" 2>&1
  code=$?
  set -e
  docker logs "$player" > "$dir/player.log" 2>&1 || true
  docker rm -f "$player" >/dev/null 2>&1 || true; docker network rm "$net" >/dev/null 2>&1 || true
  if [ -f "$dir/out/result.json" ]; then
    say "$solver: done in $(( $(date +%s) - t0 ))s, raw_scores=$(grep -oE '"raw_scores": \[[^]]*\]' "$dir/out/result.json" || head -c 80 "$dir/out/result.json")"
  else
    echo "$solver: referee exited $code without result.json; last lines:" >&2; tail -5 "$dir/referee.log" >&2; return 1
  fi
}

run() {
  check_local
  IFS=',' read -r -a list <<< "$SOLVERS"
  for s in "${list[@]}"; do run_one "$s"; done
  say "all runs finished; results under $BASE/<solver>/out/result.json"
}

import_results() {
  IFS=',' read -r -a list <<< "$SOLVERS"
  local digests; digests=$(printf '{"player": "%s", "referee": "%s"}' "$PLAYER" "$REFEREE")
  for s in "${list[@]}"; do
    [ -f "$BASE/$s/out/result.json" ] || { say "$s: no result.json, skipped"; continue; }
    (cd "$ROOT/backend" && .venv/bin/python -m app.arena.apex_local import "$PID" "$s" "$BASE/$s" "$digests")
  done
}

case "$CMD" in
  verify) verify ;;
  pull) pull ;;
  run) run ;;
  import) import_results ;;
  all) verify; pull; run; import_results ;;
  *) sed -n 2,13p "$0"; exit 2 ;;
esac
