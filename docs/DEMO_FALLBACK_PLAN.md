# Demo fallback plan

Date: 2026-10-29. Demo: end of this week. Competition: `concours_fraud_6974713c0ea7` v0.1.0, filed as
[macrocosm-os/apex-competitions-builder#47](https://github.com/macrocosm-os/apex-competitions-builder/issues/47),
waiting on Macrocosmos. Images: `ghcr.io/parry22/concours-fraud-player` and `-referee`, private, cosign-signed
by the release workflow, `linux/amd64` only.

## Summary for the founder

Plan B is the demo. It runs the exact signed images from GHCR on the laptop, through the same referee and
player contract Apex uses, with four solvers, and feeds the results into the Improve screen with a clear
"Apex-compatible local run" label. It works with the Wi-Fi off once the images are pulled the night before.
If Macrocosmos activates the competition on testnet in time (Plan A), the same screen shows "Live on Apex
testnet" with the real results, and Plan B stays ready as the fallback. Plan C (a run on GitHub's servers)
is a nice extra that shows the run happening off the laptop; do it only if everything else is done.

Recommendation: rehearse Plan B offline on the demo laptop by Thursday, record the screen, and treat Plan A as a
bonus. Never say "live on Apex" unless the Apex dashboard shows the round.

## Plan A: Apex testnet activation

Only if Macrocosmos replies in time. Steps:

1. Access, least privilege. On GitHub, open each package under your profile (Packages: `concours-fraud-player`,
   `concours-fraud-referee`), Package settings, Manage Actions access / Manage access, add the GitHub account
   Macrocosmos names with **Read**. Do not add them to the repo: `spec.yaml` is in the issue and `HANDOFF.md` can
   be attached there. If they insist on repo access, add them as a read-only collaborator and remember the
   holdout is in that repo's history (security audit 3.1).
2. Confirm what they activate: competition id, version (`0.1.0` unless v0.2.0 is filed first), network
   (stage or testnet netuid 61), round length (2 days in the spec), and where results are shown.
3. Monitor. Ask for the dashboard URL and the registry entry. Check: the round is open, at least one submission
   (the baseline) was evaluated, `result.json` was produced (they can share it), the score matches a local run
   of the same submission to four decimals (determinism check).
4. Capture. Screenshots of: the registry entry, the round page, one evaluation with its score; save
   `result.json` as `workspace/<pid>/apex/<round>/result.json`.
5. UI. Set `CONCOURS_APEX_STATUS=testnet` in `backend/.env` so the Improve screen's run badge reads "Live on
   Apex testnet" and the Launch screen's validation card links to the dashboard. Without that variable the badge
   says "Apex-compatible local run". Never set it by hand without a live round.
6. Keep Plan B ready: the pulled images and cached results are on the laptop regardless.

## Plan B: Apex-compatible local run (mandatory)

What it is: `scripts/apex_local_run.sh` pulls the two signed images by digest from `spec.yaml` of the
competition repo, verifies both cosign signatures against the workflow identity, then runs the referee against
each of four submissions in turn on an internal Docker network, exactly as the arena does: baseline
(`baseline_logreg`), standard model (`lgbm_default`), tuned model (`lgbm_tuned`), drift-aware model
(`lgbm_velocity`). Each run writes `result.json`; the script imports the four results into the project as
scored attempts (origin `apex_local`), so the Improve screen, the gates and promotion work on them like any
round. A completed run is cached, so replaying takes seconds.

Flow per submission (same as `backend/app/arena/runner.py`, which is what the toolkit's documented loop does):

```
docker network create --internal <net>
docker run -d --name <player> --network <net> --cpus 2 --memory 2g --cap-drop ALL --security-opt no-new-privileges \
  --read-only --tmpfs /tmp --pids-limit 256 -v <submission.py>:/app/submission.py:ro <player image@digest>
docker run --rm --network <net> --cpus 1 --memory 1g --cap-drop ALL --security-opt no-new-privileges \
  -e MATCH_ID=<id> -e SEED=0 -e NUM_PLAYERS=1 -e PLAYER_URLS=http://<player>:8000 \
  -e CONFIG_JSON="$(cat fixtures/input.json)" -v <out>:/data <referee image@digest>
```

Complications, and what the script does about each:

- **Private GHCR pulls.** The laptop needs `docker login ghcr.io` with a token that has `read:packages` only
  (a fine-grained PAT; not the `gh` token, which has `repo` and `workflow`). The script checks
  `docker manifest inspect` first and prints the login command when it fails. In Actions (Plan C) the
  `GITHUB_TOKEN` of the competition repo has package read.
- **Architecture.** The signed images are `linux/amd64`; the demo laptop is Apple Silicon. Docker Desktop
  runs them under Rosetta. Measured on this laptop: see "Measured" below. If the emulated run is too slow for
  the demo, the release workflow for v0.2.0 builds `linux/amd64,linux/arm64` with `buildx`, and cosign signs
  the index, so the arm64 image is covered by the same signature. Until then, the script also accepts
  `--platform linux/arm64` to run a locally built image, but then labels the run "local build, unsigned".
- **Venue Wi-Fi.** `scripts/apex_local_run.sh pull` the night before stores both images locally and records
  the verification result in `.cache/apex_local/<competition id>/verified.json` with the digests (outside `workspace/`, so `scripts/demo.sh` keeps it). `run` works with the
  network off: it re-checks the local image digest against the pinned one and skips the cosign online step if
  `verified.json` is fresh (cosign verification needs the Rekor transparency log, which is online; the
  verification result is recorded offline). Completed runs are cached under `.cache/arena/` like every arena
  result, so the Improve screen replays in seconds.
- **Logs.** The referee logs row counts and scores, never rows; the script tails only `result.json` and the
  last five referee log lines. Runner time: a full four-solver run on amd64-under-Rosetta is the slow path;
  the baseline is the fastest, so run that first and show it if time is short.
- **Honesty.** The run badge on Improve reads "Apex-compatible local run (signed Apex images)" and the attempt
  rows carry the origin "apex_local". Nothing says "live" unless `CONCOURS_APEX_STATUS` is set by Plan A.
  The Launch screen's validation step says "local run of the signed images" and names the digests.

Pre-demo checklist (Plan B):

- [ ] Wednesday: on the demo laptop, create a fine-grained GitHub PAT with package read only, then
      `docker logout ghcr.io && docker login ghcr.io -u parry22` with that PAT (never the `gh` token).
- [ ] Wednesday: `scripts/apex_local_run.sh verify && scripts/apex_local_run.sh pull`.
- [ ] Wednesday: `scripts/demo.sh` with the laptop off the venue network; afterwards set `CONCOURS_SIGNUP=invite` in
      `backend/.env` so nobody else can create an account.
- [ ] Wednesday: `scripts/apex_local_run.sh run` with Wi-Fi on, all four solvers. Note the total time.
- [ ] Thursday: Wi-Fi off, `scripts/demo.sh` (keeps `.cache/`), `scripts/dev.sh`, open the project, Improve:
      the four attempts replay from cache in seconds. Then `scripts/apex_local_run.sh run --fresh` for one
      solver to prove a cold run works offline.
- [ ] Thursday: screen recording of a complete successful run (QuickTime, the whole Improve screen), saved to
      the laptop and a USB stick.
- [ ] Thursday night: laptop charged, Docker Desktop started, images present (`docker images | grep concours-fraud`),
      both dev servers tested on `127.0.0.1` only.
- [ ] Demo day: `scripts/dev.sh` before leaving for the venue; do not update Docker Desktop or macOS.

## Plan C: remote run on GitHub Actions (optional)

A workflow in the competition repo, `.github/workflows/local-run.yml` (manual trigger, `workflow_dispatch`
with a `solver` input): checks out the repo, logs in to GHCR with `GITHUB_TOKEN`, verifies both images with
cosign, runs the same two-container loop on the runner (amd64, no emulation), uploads `out/result.json` as an
artifact, and commits nothing. The app reads it through `scripts/apex_local_run.sh import --from-actions <run id>`
(`gh run download`), which stores it as an attempt with origin `apex_actions`. Logs print row counts and the
score only; the holdout never leaves the image. Runner limits: 6 hours per job, far above the 5170 s referee
timeout. Dependence: needs network at demo time to show the run page; so do it the day before and show the
artifact page.

## Recommendation

Plan B, rehearsed offline, with the recording as the last resort. Plan A only on top of a passing Plan B.

## Measured on this laptop (Phase 2, 2026-10-29)

Apple Silicon (arm64), Docker Desktop 29.5, the signed v0.1.0 images (linux/amd64, emulated):

| Step | Result |
|---|---|
| `cosign verify` of both images against the release workflow identity | pass (player `sha256:cc491c83...`, referee `sha256:06ea0c32...`) |
| `docker pull` by digest | both present |
| `run` baseline_logreg | 125 s, `raw_scores: [3713.534]` (filed: 3713.5343) |
| `run` lgbm_default | 132 s, `raw_scores: [3706.485]` |
| `run` lgbm_tuned | 986 s, `raw_scores: [3960.634]` (filed: 3960.6343) |
| `run` lgbm_velocity | 877 s, `raw_scores: [3922.553]` |
| `import` of the four results | four attempts with origin `apex_local` on the Improve screen; gates evaluated against v2; none promoted (correct: none beats v2) |
| replay of cached results in the Improve screen | seconds |

Every score matched the filed v0.1.0 numbers to four decimals, so the laptop run is the platform run. The tuned
model's 16 minutes is the emulation cost; the v0.2.0 release workflow builds arm64 images too, after which the
same run is native. The v0.2.0 referee (branch `v0.2.0` of the competition repo) was built and run natively from
the repo: baseline lift -0.0054 (the logistic baseline is a hair under the largest-payments rule), money per day
unchanged, private number absent from `result.json` metadata and present in `details.json`.

v0.2.0 released 2026-10-29 (amd64 and arm64, cosign verified, `HOLDOUT_KEY` set). Native run of the four solvers
with the signed v0.2.0 images on this laptop: 17 s, 10 s, 310 s, 66 s (404 s in all); lifts -0.0054, -0.0089,
0.1171, 0.0983. The demo can use either: v0.1.0 results are imported and replay instantly; v0.2.0 images run
natively in under seven minutes for all four.

Plan C: `local-run.yml` ran green on a GitHub runner (run 40868194709): signatures verified, baseline scored
-0.0054 lift, `result.json` and `details.json` uploaded as an artifact.
