# Judge day runbook (demo on 2026-10-31)

Final check made the night before (2026-10-30). Everything below was run on this laptop that evening; nothing is
assumed. Read this file, nothing else, before the demo. `docs/DEMO_SCRIPT.md` is the 3-minute script itself.

## Where things stand

| Item | State |
|---|---|
| Backend tests | 167 pass (`cd backend && .venv/bin/python -m pytest -q`) |
| Frontend | copy lint clean, type check clean (`cd frontend && pnpm test`) |
| Marketing site | `website/` builds (`NEXT_DIST_DIR=.next-build pnpm build`) |
| Demo workspace | seeded and ready in `workspace/`: "Card fraud review queue, Q4" (v2, not yet jumped forward), "Marketplace payments" (v1, slipping, round ready), "Card fraud on Bittensor" (v2 credited to an outside solver on a local chain) |
| Signed-image runs | the four Apex v0.2.0 results are imported into the Q4 project as "signed-image runs" and kept under `.cache/apex_local/`, so a reseed keeps them |
| Sign-in | `demo@concours.local`, password in `.env` at the repo root (reset on 2026-10-30; the browser's saved session also works for 14 days) |
| Apex (Macrocosmos) | competition `concours_fraud_6974713c0ea7` v0.2.0 is released and signed on `parry22/concours-fraud`; onboarding issue #47 is open, unlabelled, no reply. Not activated anywhere. Never say "live on Apex". |
| Git | remote `origin` = private `parry22/concours` (added 2026-10-30); `claude/website` is pushed and holds everything (master is 33 commits behind it). |

## The link to give judges (hosted copy, free)

**https://concours-demo-49wqv46v5pghxqr-3000.app.github.dev**

That is the product running in a GitHub Codespace (4 cores, 16 GB, Docker inside) created from the private repo
`parry22/concours`, branch `claude/website`, on the personal free quota. Verified on 2026-10-30: the seeded
workspace (both projects, the four signed-image runs with gates against v2), sign-in through the frontend proxy,
and the public page. The laptop is not involved; judges can open it on a phone.

What they see first: GitHub's one-time page "You are about to access a development port served by someone's
codespace" with a **Continue** button. Tell them to press it. After that the Concours sign-in page. Sign-in is
required and sign-up is closed (`CONCOURS_SIGNUP=first`, the owner exists), so judges need the credentials from
`.env` at the repo root (the hosted owner is the same `demo@concours.local` with the same password as the laptop).
Give them to a judge in person, never in the deck.

Rules of the hosted copy:

- It stops after 4 hours without a client session (the maximum). Visits to the link do not count as activity;
  only an open ssh or editor session does. The servers do not survive a stop. `scripts/hosted.sh` wraps the gh
  commands:

  ```bash
  scripts/hosted.sh wake
  ```

  starts the codespace if needed and (re)starts the API and the frontend, then prints the link. During the demo keep

  ```bash
  scripts/hosted.sh keepalive
  ```

  running in a terminal on the laptop so the codespace is not stopped mid-demo. `scripts/hosted.sh status` and
  `scripts/hosted.sh logs` for a look. The seeded workspace and the caches are on the codespace disk and survive
  stops. Before leaving for the venue: `scripts/hosted.sh wake`, open the link once so the first page load is warm,
  then `scripts/hosted.sh keepalive`.
- The improvement rounds replay from `.cache/arena` (copied in), so the scripted demo runs in seconds there too.
  A round that is not cached runs in Docker inside the codespace (the Docker images build on first use, a few minutes).
- Free quota: 120 core-hours a month on a personal account, so about 30 hours on this 4-core machine. The
  codespace is kept for 30 days after its last stop, then deleted. `gh codespace list` shows it; `gh codespace delete`
  removes it when the demo is over.
- It is public to anyone with the link, behind sign-in. If the password leaks, reset it in the codespace:

  ```bash
  gh codespace ssh -c concours-demo-49wqv46v5pghxqr -- 'cd /workspaces/concours/backend && .venv/bin/python -m app.admin reset-password demo@concours.local'
  ```

How it was built (for a rebuild): `.devcontainer/devcontainer.json` (universal image, 4 cores, port 3000 forwarded),
`.devcontainer/setup.sh` (uv, Python 3.11, pnpm), `.devcontainer/start.sh` (API on 127.0.0.1:8000, production
frontend on 0.0.0.0:3000). `data/`, `.cache/arena`, `.cache/serving`, `.cache/apex_local` and `.env` are not in git
and were copied in over `gh codespace ssh -- 'cat > file' < file`; the competition `spec.yaml` sits at
`/workspaces/apex-spec/spec.yaml` and `APEX_REPO=/workspaces/apex-spec scripts/demo.sh` seeds and imports. Then
`gh codespace ports visibility 3000:public -c <name>`. Caches go to `/tmp` there (the 32 GB root disk is mostly the
image); the first dependency install ran out of disk and left a broken numpy, so `rm -rf backend/.venv && uv sync`
if the API dies on `import numpy`.

Rehearsed there on 2026-10-30 with `scripts/e2e_check.py` (a throwaway project, deleted afterwards): sample
project 6 s, protection 13 s, v1 4 s, tuned contest 3 s (v2, $3,961 a day), jump forward 4 weeks with a round
38 s (v3, $6,543 a day), 76 s in all. The rounds replayed from the copied cache, no Docker build was needed. The
numbers are the ones in `docs/DEMO_SCRIPT.md`.

Agent attempts ("Add an agent attempt" on Improve) use the Claude CLI on your subscription. Signed in on the laptop
and on the hosted copy (done 2026-10-30; the sign-in lives in the codespace's home directory and survives stops). If the
hosted button ever answers "no model available", sign in again from this machine:

```bash
scripts/hosted.sh claude-login
```

It prints a URL to open here and asks for the code.

To push tonight's commits to the hosted copy (fetch, dependencies, frontend rebuild, restart; about 3 minutes):

```bash
scripts/hosted.sh deploy
```

The laptop path below is the fallback if the codespace or the venue network fails.

## The easiest demo path

Plan B from `docs/DEMO_FALLBACK_PLAN.md`: the product on this laptop, offline, with the signed Apex images already
run and imported. Nothing needs the network.

1. Quit anything else on port 3000. On 2026-10-30 another project's `next dev` (per-second-compute) was listening
   there; `scripts/dev.sh` would then start the frontend on a different port and the script's URLs would be wrong.
   `lsof -nP -iTCP:3000 -sTCP:LISTEN` shows the process.
2. Docker Desktop running (the jump-forward round and any fresh run need it).
3. `./scripts/dev.sh` from the repo root. Backend on 8000, frontend on http://localhost:3000.
4. Open http://localhost:3000. If signed out, sign in with the credentials in `.env`.
5. Follow `docs/DEMO_SCRIPT.md`. The Improve tab of the Q4 project lists seven attempts: three local, four marked
   "Scored on this machine with the signed Apex referee and player images (not a live network run)".

Do not run `scripts/demo.sh` on the day unless the workspace is broken. It wipes `workspace/`, reseeds both projects
and re-imports the signed-image runs; measured on 2026-10-30 with the arena cache warm: see "Reseed rehearsal" below.
The old failure (the wipe deleted the signed-image results and the importer pointed at a project id that no longer
existed) is fixed: results live under `.cache/apex_local/` and the importer finds the project by name.

If the laptop must be reset anyway:

```bash
cd /Users/parry/concour && ./scripts/demo.sh && ./scripts/dev.sh
```

A cold signed-image run, live, one solver (native arm64 images, about 20 s for the baseline):

```bash
cd /Users/parry/concour && scripts/apex_local_run.sh run --solvers baseline_logreg --fresh && scripts/apex_local_run.sh import
```

## Apex, the fork question, and what to say

**Can we fork the Apex subnet repo and run the competition ourselves?** No. The public `macrocosm-os/apex`
validator does not evaluate submissions; it asks Macrocosmos's orchestrator for scores and sets weights from them.
A fork of it has nothing to score with. The competition package (`parry22/concours-fraud`) is complete and signed;
only Macrocosmos can activate it, and they have not answered the issue or the email.

**What runs instead, and is honest:**

- The signed Apex images (player and referee, cosign-verified against the release workflow identity) run on this
  laptop through the exact referee/player contract Apex uses. The scores match the filed numbers to four decimals.
  The UI calls them "signed-image runs" and says "not a live network run".
- Concours as the validator of its own Bittensor subnet (`subnet/`). Verified on a local chain on 2026-10-28: a
  miner committed the velocity solver's hash on chain, uploaded it, Concours scored it in the sandbox, it passed
  the five gates and became v2 credited to the miner's uid ($6,543 a day against $4,685). The seeded project
  "Card fraud on Bittensor" shows that result. Weights were not set on the local chain (the old devnet image
  hangs on commit-reveal); on testnet they would be, but testnet needs test TAO from the Bittensor Discord, which
  we do not have.
- Do not start the local chain live on this laptop during the demo. It has 8 GB of memory; the chain container was
  killed by the kernel (exit 137) last time it ran next to the app and Docker. Show the seeded project instead.

- **Outside solvers without any chain (added 2026-10-30).** The "Outside solvers" card on Improve creates a solver
  key per person. A solver anywhere runs `concours solve kit --key sk_… --url <link>/api`, writes `submission.py`,
  runs `concours solve submit submission.py`; Concours scores it in the sandbox on the private holdout, through the
  five gates, and promotes it credited to their name ("Outside solver: Ada"). This is the solver loop running for
  real, today, with no Macrocosmos and no TAO. Verified on the hosted copy with a cold upload of a messy customer
  file and the velocity solver sent as an outside submission (`scripts/e2e_outside.py`). Live in front of a judge:
  create a key on Improve, hand them the command, or run it yourself from the laptop against the hosted link.

**If asked "is this on Apex?"**: "The competition is filed and the package is signed. Macrocosmos has not activated
it yet, so what you see are the signed Apex images run on this machine, plus the same loop running as our own
Bittensor subnet on a local chain."

## The model: no changes tonight

The fraud model is left as it is, on purpose:

- Every solver change changes the arena cache key, so every seeded run would rebuild in Docker (minutes per solver
  on this laptop) and every number in the demo script would move.
- The signed v0.2.0 images were built from the current solvers; a change here would no longer match them.
- The story already works: before the jump, no attempt beats v2 (lift 0.117, the bar); after the jump into the
  card-testing pattern, the velocity solver passes all five gates and becomes v3 at $6,543 a day against $4,840.
  That is the point of the gates: the new pattern is not in older labels, so only a solver with velocity features
  and card-testing rules catches it.

Judge questions on the modelling are answered at the end of `docs/DEMO_SCRIPT.md`.

## Reseed rehearsal (2026-10-30)

`scripts/demo.sh` was run into a spare workspace (`CONCOURS_WORKSPACE=.../workspace-rehearsal`, backend on 8001) so
the live workspace stayed untouched:

| Step | Measured |
|---|---|
| wipe, backend start, sign-up of the demo owner | 30 s |
| "Card fraud review queue, Q4": create, map, three questions, protect, v1, round (replayed from `.cache/arena`), labels | 55 s |
| "Marketplace payments": create, protect, v1, jump 4 weeks, slipping | 40 s |
| import of the four signed-image runs (gates against v2, one local re-fit) | 3.5 min |
| total | about 6 minutes |

Result: both projects as the script expects (Q4 at v2, $3,961 a day, not yet jumped; Marketplace jumped and slipping);
the Improve tab of Q4 lists the four signed-image runs with the same money figures as the live workspace
($3,713.5, $3,706.5, $3,960.6, $3,922.6 a day), gates evaluated against v2, none promoted. Signed in with the
`.env` credentials in a fresh browser session.

## Before leaving for the venue

- [ ] Laptop charged; Docker Desktop started; do not update Docker Desktop or macOS.
- [ ] Port 3000 free; `./scripts/dev.sh`; sign in; open the Q4 project once so the first page load is warm.
- [ ] Wi-Fi can be off: the three questions are parsed in code, no language model call is made for fraud.
- [ ] `git push origin claude/website` so the private GitHub repo has tonight's commits.
- [ ] `scripts/hosted.sh wake`, open the hosted link once, then leave `scripts/hosted.sh keepalive` running.
