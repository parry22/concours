# Judge day runbook (demo on 2026-10-31)

Final check made the night before (2026-10-30). Everything below was run on this laptop that evening; nothing is
assumed. Read this file, nothing else, before the demo. `docs/DEMO_SCRIPT.md` is the 3-minute script itself.

## Where things stand

| Item | State |
|---|---|
| Backend tests | 159 pass (`cd backend && .venv/bin/python -m pytest -q`) |
| Frontend | copy lint clean, type check clean (`cd frontend && pnpm test`) |
| Marketing site | `website/` builds (`NEXT_DIST_DIR=.next-build pnpm build`) |
| Demo workspace | seeded and ready in `workspace/`: "Card fraud review queue, Q4" (v2, not yet jumped forward), "Marketplace payments" (v1, slipping, round ready), "Card fraud on Bittensor" (v2 credited to an outside solver on a local chain) |
| Signed-image runs | the four Apex v0.2.0 results are imported into the Q4 project as "signed-image runs" and kept under `.cache/apex_local/`, so a reseed keeps them |
| Sign-in | `demo@concours.local`, password in `.env` at the repo root (reset on 2026-10-30; the browser's saved session also works for 14 days) |
| Apex (Macrocosmos) | competition `concours_fraud_6974713c0ea7` v0.2.0 is released and signed on `parry22/concours-fraud`; onboarding issue #47 is open, unlabelled, no reply. Not activated anywhere. Never say "live on Apex". |
| Git | this repo has no remote: every branch exists only on this laptop. `claude/website` holds everything (master is 33 commits behind it). |

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
- [ ] Back this repo up: it has no git remote. At least `git bundle create ~/concour-$(date +%F).bundle --all` onto a USB
      stick, or push every branch to a private GitHub repo.
