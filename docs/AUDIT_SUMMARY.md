# Audit summary

Date: 2026-10-29. Branch `claude/audit-and-demo-fallback` (14 commits on top of the merged Apex-onboarding work).
Reports: `docs/audits/SECURITY_AUDIT.md`, `docs/audits/CUSTOMER_JOURNEY_AUDIT.md`, `docs/DEMO_FALLBACK_PLAN.md`,
`docs/ISSUE_47_UPDATE.md`.

## The five most important things found

1. **The hidden answers are copyable by anyone with read access.** The private holdout is committed to the
   competition repo and baked into the referee image, as the Apex contract requires. Keep both private, give
   Macrocosmos read access to the two packages only, and move to an encrypted holdout in the repo for a later
   release. Not fixable this week without changing the Apex contract.
2. **On venue Wi-Fi anyone could sign in as you.** The app listened on every interface and the demo password was
   committed. Fixed: the app binds to the laptop only and the seed generates a password into the gitignored `.env`.
3. **Code written by the agent solver ran on the laptop, outside the sandbox**, to score the queue. Fixed: such code
   is scored inside the player container; the host imports only the built-in solvers.
4. **The competition's scoring rule left solvers almost nothing to win**: "review the largest payments" scored 94%
   of the bar. Fixed as v0.2.0 (lift over that rule; a trivial submission scores 0, today's model 0.117). v0.1.0 is
   untouched; the note for issue #47 is drafted, not posted.
5. **A real customer's CSV stopped the product at the second screen** (mixed date formats, currency symbols, blank
   amounts), and a sparse file crashed the queue. Fixed: tolerant parsing with plain-English notes, and protection
   refuses an empty test window with a sentence.

## What was fixed (one commit each)

Security: localhost bind and generated demo password; Excel-safe CSV exports; hardened arena containers (no
capabilities, no privilege escalation, read-only root, pid limits); outside code scored only in the sandbox;
cosign verification before any pulled image runs; v0.2.0 lift scoring with the private number kept out of
result metadata; Actions pinned by commit SHA and base images by digest with least-privilege workflow jobs.
Also: the detached-row error at the end of every fresh arena run.

Demo: Plan B (`scripts/apex_local_run.sh`) runs the exact signed v0.1.0 images on this laptop and feeds the
results into the Improve screen as "signed-image runs"; a live-versus-local indicator on Improve, Launch and
the Trust page; Plan C workflow template (`local-run.yml`) in the v0.2.0 package, untested on a runner.

Customer journey: tolerant upload with date range and notes; empty-window guard; 5% random checks in the
queue; versus-your-current-tool; the Visa 1.5% ratio card; what-changed per version; a Trust page; the demo
jump control hidden on real projects.

## What remains, and why

- Every Medium and Low finding is now fixed in code or documented as accepted (3.4: the protected files stay in
  clear on the laptop because Docker builds from them; 1.3 and 6.2 are laptop steps in the demo checklist).
- The v0.1.0 commit in the competition repo still holds the holdout in clear in git history; v0.2.0 commits it
  encrypted. Rewriting that history is the founder's call.
- v0.2.0 is released: tag `v0.2.0` on `parry22/concours-fraud`, digests pinned on `main` at `918b1a3`
  (player `sha256:f83dfa64...`, referee `sha256:ba26636b...`), both indexes amd64 and arm64, both verified
  with cosign, `HOLDOUT_KEY` secret set. The issue #47 comment is written but not posted: posting to an
  external issue was blocked for this session, so run the command in `docs/ISSUE_47_UPDATE.md` yourself.
- Macrocosmos package read access: waiting on the account name they give.
- Journey items tagged later: case management, alerts and digests, rules with backtests, dispute-file import,
  webhooks and API, progress estimates for cold Docker runs.
- Plan C ran green on a GitHub runner (run 40868194709: signatures verified, baseline lift -0.0054, artifact uploaded).

## Which demo plan to use

Plan B, rehearsed offline. The four signed v0.1.0 images ran on this Apple Silicon laptop under emulation:
baseline 125 s, standard model 132 s, tuned model 986 s (16 minutes), drift-aware model 877 s. Scores matched
the filed numbers to four decimals ($3,713.53, $3,706.48, $3,960.63, $3,922.55 per day); the four results were
imported into the sample project and show on Improve as signed-image runs, with gates evaluated against v2. Replays are instant.
If Macrocosmos activates in time, set `CONCOURS_APEX_STATUS=testnet` and show the real round on top (Plan A).

## v0.2.0 images on this laptop (native arm64, no emulation)

baseline 17 s (lift -0.0054), standard 10 s (-0.0089), tuned 310 s (0.1171, the bar), drift-aware 66 s (0.0983);
404 s for all four. The same referee on a GitHub runner gave the baseline the same lift to all decimals.

## If Apex does not activate in time: the "just fork it" path

The public `macrocosm-os/apex` validator does not evaluate anything itself; it asks Macrocosmos's orchestrator for
scores and sets weights. Forking it therefore cannot run this competition. What a fork can do, and what the repo
already contains, is Concours as the validator of its **own** testnet subnet: `subnet/README.md` has the runbook
(wallets, test TAO from the Bittensor Discord, `register-subnet`, `start-call`, miner registrations, stake, then
`concours-validator` and `concours-miner submit`). Outside solvers commit a hash on chain, upload their
`submission.py`, and Concours scores it through the same sandbox and gates; the Improve screen shows "Bittensor
testnet, netuid N". That is a live network run of the same model-improvement loop, without Macrocosmos. The steps
that create keys and spend TAO are yours to run.

## Commands

The night before (needs network, once):

```bash
cd /Users/parry/concour && scripts/apex_local_run.sh verify && scripts/apex_local_run.sh pull
```

```bash
cd /Users/parry/concour && scripts/apex_local_run.sh run && scripts/apex_local_run.sh import
```

Demo day (works offline):

```bash
cd /Users/parry/concour && ./scripts/demo.sh && ./scripts/dev.sh
```

Then open http://localhost:3000, project "Card fraud review queue, Q4", Improve: the signed-image runs are
listed as attempts with the badge "Apex-compatible local run". To show a cold run live, one solver:

```bash
cd /Users/parry/concour && scripts/apex_local_run.sh run --solvers baseline_logreg --fresh
```

Backend tests: `cd backend && .venv/bin/python -m pytest -q` (154 pass). Frontend: `cd frontend && pnpm test`.
