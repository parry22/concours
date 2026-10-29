# Concours security audit

Date: 2026-10-29. Scope: this repository (branch `claude/audit-and-demo-fallback`, which merges the Apex
onboarding branch so the audited code is the code that produced the filed competition), the private
competition repo `parry22/concours-fraud` at `dab9c38` (v0.1.0, local clone `/Users/parry/concours-fraud-repo`),
its two GHCR packages, and the GitHub Actions workflows. Read-only: nothing was changed while auditing.
Fixes for the Critical and High findings are in the Phase 2 commits on this branch; `docs/AUDIT_SUMMARY.md` says
which ones landed.

## Summary for the founder

The product is in better shape than most prototypes: passwords are hashed properly, uploads and the ID map are
encrypted on disk, card numbers are removed before anything is written, the solver sandbox has no internet, and
the referee validates every score it receives. Nothing secret (keys, tokens, customer data) was ever committed to
this repository's git history.

Five things matter before the demo and the Apex filing:

1. **The hidden answers are in two places anyone with read access can copy.** The private holdout (the rows and
   labels every version is judged on) is committed to the `concours-fraud` repo and baked into the referee image
   on GHCR. That is required by the Apex contract, but it means: whoever Macrocosmos names gets the answers, and
   if either the repo or the package ever flips to public, the competition is worthless. Keep both private, give
   Macrocosmos package read access only (not repo access), and plan v0.2.0 so the holdout is encrypted in the
   repo and decrypted only inside the release workflow.
2. **On venue Wi-Fi, anyone can sign in as you.** The demo owner's password is in `.env.example` (committed), and
   the web app listens on every network interface. A person on the same Wi-Fi opens `http://<your-laptop>:3000`,
   signs in with the committed password, and sees the customer's queue. Fix: bind the app to the laptop only and
   generate a fresh demo password at seed time. (Fixed in Phase 2.)
3. **Downloaded CSVs could carry Excel formulas.** A transaction ID in the customer's file that starts with `=`
   ends up in the review-queue CSV unchanged, and Excel runs it. Fix: escape those cells. (Fixed in Phase 2.)
4. **Code written by the agent solver runs on your laptop, not in the sandbox**, when it is promoted to a version
   and used to score today's queue. The sandbox protects the competition run only. Fix: score the queue through
   the same player container, or only ever promote built-in solvers until that exists. (Mitigated in Phase 2:
   agent-written and outside code is no longer loaded on the host; the queue and gates use scores produced in the
   sandbox.)
5. **The scoring rule leaves solvers almost nothing to win.** "Review the 200 largest payments" already scores
   94% of today's model. v0.2.0 should score lift over that rule, so that a solver's number says how much of the
   remaining catchable fraud it found. Never edit v0.1.0 in place; file v0.2.0 and note it on issue #47.

Everything else is Medium or Low: container hardening flags, pinning Actions and base images, keyed hashing of
customer IDs, timestamps that could re-identify a customer, and a handful of error messages that leak file paths.

## Threat model

Assets:

| Asset | Where it lives | Who must never see it |
|---|---|---|
| Customer transactions (raw and canonical) | `workspace/<pid>/raw.csv`, `dataset.csv` (encrypted, `CONCOURS_DATA_KEY`), `private/recent.csv` | anyone outside the customer's organisation |
| ID map (hash to real customer and merchant IDs) | `workspace/<pid>/private/id_map.csv` (encrypted) | solvers, Macrocosmos, the demo audience |
| ID-hashing salt | `project.salt` column in the database (plain text); fixed strings in `scripts/seed.py` for the seeded demo projects | solvers (with it, hashes are reversible for small ID spaces) |
| Private holdout rows and labels | `workspace/<pid>/protected/holdout*.csv`, `referee/data/` in `parry22/concours-fraud` (git history included), layer in `ghcr.io/parry22/concours-fraud-referee` | solvers; anyone who could tune to it |
| Anthropic API key | `backend/.env` (absent on this machine; the Claude CLI's own login is used instead) | everyone |
| GitHub tokens | `gh` keyring token (scopes `repo, workflow, read:packages, read:org, gist`), `GITHUB_TOKEN` in the release workflow (`contents: write, packages: write, id-token: write`) | everyone |
| Cosign identity | the release workflow's OIDC identity; nothing to steal, but the workflow file path is part of the identity | n/a (keep the path stable) |
| Encryption key | `workspace/.data_key` (0600) locally; `CONCOURS_DATA_KEY` in production | everyone |

Attackers:

| Attacker | Capability | Wants |
|---|---|---|
| Malicious solver (Apex miner, chain miner, the agent solver) | runs arbitrary Python in the player container; sees public train data, `transform.json`, the observation batches (holdout features without labels) | the labels, the ID salt, a higher score without a better model, escape to the host |
| Curious validator (Macrocosmos operator, platform runner) | runs the referee image; reads its layers; sees `result.json` and `trace.jsonl` | nothing malicious assumed, but they can read the holdout |
| Anyone who can pull the images | read access to the GHCR packages (named collaborators, a leaked token, GitHub staff) | the holdout |
| External attacker on the web app | HTTP to the API or the Next.js server | sign in, read a queue, upload a file, exhaust resources |
| Supply-chain compromise | a moved Action tag, a replaced base image, a poisoned pip or npm package | run code in CI or on the laptop |
| Demo audience on shared venue Wi-Fi | same L2 network as the laptop; can reach any port the laptop listens on | sign in as the demo owner, screenshot the queue, DoS the demo |

## Findings

Severity: Critical, High, Medium, Low. Effort: under 1 hour, a few hours, days.

### 1. Secrets

| # | Severity | Finding |
|---|---|---|
| 1.1 | Low | **No secrets or data in git history.** Checked every commit on every branch for API keys, tokens, private keys, passwords, `.env`, data files and blobs over 2 MB (gitleaks and trufflehog are not installed on this Mac; a regex sweep over `git log -p` and `git rev-list --objects --all` was used instead). The only hits are `.env.example` and the word "Password" in a UI label. Evidence: `git log --all -p` sweep, `git ls-files` (only `.env.example` tracked). Fix: install gitleaks in CI (`gitleaks/gitleaks-action`) so this stays true. Effort: under 1 hour. |
| 1.2 | High (demo) | **Demo owner password is committed and used by default.** `.env.example:11` holds `CONCOURS_DEMO_PASSWORD=demo-TRfA8wQBZa6p`; `scripts/seed.py` (`_env_file`) reads `.env.example` first and `.env` second, and neither `.env` nor `backend/.env` exists on this machine, so the seeded owner account uses the committed password. Combined with 6.1 (the web app listens on all interfaces), anyone on venue Wi-Fi can sign in as the owner. Attack: open `http://<laptop-ip>:3000`, log in with the password from GitHub, download the review queue. Fix: seed generates a random password and writes it to `.env` (gitignored) when none is set; `.env.example` keeps only a placeholder. Effort: under 1 hour. |
| 1.3 | Medium | **GitHub token on the laptop is broader than pulling needs.** `gh auth status` shows `repo, workflow, read:packages, read:org, gist`. Pulling the private images needs `read:packages` only; the release workflow needs `packages: write` and `contents: write` (for the pin commit), which it has via `GITHUB_TOKEN`, scoped to that repo. Fix: for the demo laptop and for any CI that only pulls, use a fine-grained PAT with package read only, stored in the keychain by `docker login`. Effort: under 1 hour. |
| 1.4 | Low | **`.gitignore` and `.dockerignore` are correct.** `workspace/`, `.env`, `backend/.env`, `deploy/.env`, `.cache/`, datasets and pickles are ignored; the Docker build context excludes `workspace`, `data`, `.env` files and logs. The production compose passes secrets through `env_file`, not build args. No change needed. |
| 1.5 | Low | **Fernet data key is auto-generated into `workspace/.data_key` in development** and `make clean`/`scripts/demo.sh` wipe `workspace/*` (dotfiles survive `rm -rf workspace/*` only because the glob skips them). If the key is lost, encrypted uploads become unreadable. Fix: `scripts/demo.sh` should preserve or explicitly regenerate the key; production already requires `CONCOURS_DATA_KEY`. Effort: under 1 hour. |

### 2. Data leaving the machine

| # | Severity | Finding |
|---|---|---|
| 2.1 | Low | **The fraud path sends nothing to any model.** The three questions are parsed in code (`backend/app/fraud/intake.py`), the reasons are rule text (`fraud/reasons.py`), and `/intake/status` only reports the provider. The generic intake (disabled by `CONCOURS_ENABLED_TEMPLATES=fraud`) sends the profile and up to 20 sample rows with detected PII columns masked (`packager/profile.py:63`, `intake/prompts.py`), so free-text columns that the detector does not classify would reach the model there. The agent solver sends column names, dtypes, null %, unique ratio, min and max (`arena/agent_solver.py:_schema_text`), never rows. Fix: none for fraud; for the generic templates, cap sample rows to masked columns only. Effort: under 1 hour. |
| 2.2 | Medium | **ID hashing is a salted hash, not a keyed hash, and the salt is weakly protected.** `fraud/protect.py:hash_ids` computes `blake2b(f"{salt}:{value}", digest_size=8) >> 1` (63 bits). blake2b supports a `key=` parameter, which is the keyed construction; prefixing the salt is not it. The salt is stored in clear in `project.salt`, and for the seeded demo projects it is a public constant (`scripts/seed.py:29-31`). Customer IDs in the sample are small integers (0 to 4999), so with the salt, every hash reverses by brute force in seconds; without it, 63 bits is fine. If a user maps a card number column as the customer ID, it is hashed instead of dropped (`schema.drop_card_columns` skips mapped columns), and a hash over a known BIN range is reversible offline. Fix: `hashlib.blake2b(value, key=salt_bytes)`, store the salt encrypted through `secure_store` or derive it from `CONCOURS_DATA_KEY` with a per-project HKDF, and refuse a Luhn-valid customer column at mapping time. Effort: a few hours (changes the protected data hash, so cached arena results no longer replay for existing projects). |
| 2.3 | Medium | **Re-identification by timestamp and amount.** `train.csv` (in the public player image) and `holdout.csv` carry `transaction_time` to the second and `amount` to the cent with the hashed customer ID. Anyone who knows one of their own payments (time and amount) can find their hashed ID and then every other payment on that card. For a bank's real data this is a privacy incident; for the simulated sample it is harmless. Fix: round transaction time to the minute (or jitter within the minute, seeded) and amounts to whole units before staging; state this in the trust page and the data agreement. Effort: a few hours. |
| 2.4 | Low | **Card-number detection works as designed.** `packager/pii.classify_pii` flags a column when over 80% of the first 500 values are 13 to 19 digits passing Luhn, by content regardless of the column name; the float-column case is handled; `tests/test_checks.py` covers it with `4111111111111111`. Gaps: a column with fewer than 80% valid PANs (mixed with blanks over 20%) passes, and PANs embedded in free text ("card 4111...") are not caught. Fix: lower the threshold to 50% of non-null values and add a substring Luhn scan on object columns. Effort: under 1 hour. |
| 2.5 | Low | **Logs and events do not carry row data.** The request log writes method, path, status, ms, request id and org (`observability.py`); arena events carry solver names, scores and gate results; SSE replays those rows. The referee's `trace.jsonl` records a fault string (exception text, 200 chars) that could include one value from a pandas conversion error. GitHub Actions logs show `docker build` steps, not file contents (`release.yml`). Fix: truncate fault strings to the exception type only. Effort: under 1 hour. |
| 2.6 | Low | **Error messages leak local paths.** `main.py:/projects/{id}/data` returns `Could not read CSV: {e}` (pandas text, sometimes the path); `apex_builder/validate.local_run` puts `logs_path` into the validation step shown on the Launch screen; `/arena/docker` returns the Docker error string. Fix: generic messages to the client, details to the log. Effort: under 1 hour. |

### 3. Holdout protection

| # | Severity | Finding |
|---|---|---|
| 3.1 | High | **The holdout is in the competition repo's git history and in the referee image.** `parry22/concours-fraud@d19fe8b` adds `referee/data/holdout.csv`, `holdout_labels.csv`, `holdout_meta.csv` (8.4 MB, 264 KB, 2.4 MB); `referee/Dockerfile:16` copies `referee/data/` into the image; `docker history` of the local referee image shows a 17.4 MB `/app/data/` layer. Anyone with read access to the repo (collaborators, GitHub staff, a leaked token) or who can pull the package gets the answers. Today both are private and only `parry22` has access; the platform needs the image, so this is inherent to the Apex contract (hidden data must be baked in). Attack: a solver who gets the file ranks the holdout by label and scores the maximum. Fix, in two layers: (a) give Macrocosmos read access to the two packages only, not the repo (they copy `spec.yaml` from the issue); (b) in v0.2.0, commit the holdout encrypted (`age` or `openssl enc`, key in an Actions secret `HOLDOUT_KEY`), decrypt in the release job before `docker build`, and keep the plaintext out of git. The image still holds plaintext, because the platform injects only `MATCH_ID/SEED/CONFIG_JSON/PLAYER_URLS` and `CONFIG_JSON` is forwarded to the player on `/reset` (`referee.py:play_game`), so a runtime key would have to be stripped before that call; that is possible (strip `holdout_key` from `cfg` before `player.reset`) and moves trust from "anyone who can pull" to "whoever holds the registry spec", which is Macrocosmos either way. Effort: (a) under 1 hour; (b) a few hours; runtime key: a few hours and a v0.2.0 spec. |
| 3.2 | Low | **Holdout never appears in this repo or in build logs.** `workspace/` is gitignored, the handoff zip excludes `HIDDEN_FILES` (`handoff/build.py`), `zip_contains_hidden` is tested (`tests/test_handoff.py`), and the release workflow's build step logs layer names only. The repo zip (`build_repo_zip`) does include it, by design, with a README warning. No change. |
| 3.3 | Medium | **Hidden results may be visible in `result.json` metadata.** `referee.py` writes `private_score` and the full holdout split summary into `metadata`. The platform reads `raw_scores[0]` for the score; the vendored harness says anything in `metadata` is nested under the dashboard's `details`. If the dashboard shows details to miners during a round, the private number leaks per submission, which is exactly what the 7-day hidden-results term is meant to prevent. Fix: keep the holdout number only in `raw_scores`; put the leaderboard split and timings in metadata. Concours reads `raw_scores[0]` for the private score already (`arena/service.py`). Effort: under 1 hour, v0.2.0 referee. |
| 3.4 | Low | **Staged `competition/` folders for other projects sit on the laptop in clear**, as do `protected/holdout*.csv` (plain CSV, not encrypted; only raw, canonical, ID map and recent are encrypted). They are hashed IDs only, so the exposure is the labels, not identities. Fix: encrypt `protected/` at rest too, or document that the laptop disk is the trust boundary (FileVault). Effort: a few hours. |

### 4. Untrusted solver code

| # | Severity | Finding |
|---|---|---|
| 4.1 | High | **Container hardening is partial.** `arena/runner.py:run_submission` runs the player with uid 1000 (Dockerfile), `--cpus 2`, `--memory 2g`, on an `internal: true` bridge network (no internet, only the referee can reach it), submission mounted read-only, a 600 s wall-clock timeout, and the referee with 1 CPU / 1 GB. Missing: `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, `read_only=True` root filesystem (with a small `tmpfs` for `/tmp`), `pids_limit`, and the default seccomp profile is only implicit. The referee has `/data` mounted read-write (needed). No host mounts beyond the submission file and the output dir. In production, the API and worker containers mount `/var/run/docker.sock` (`deploy/docker-compose.yml`), which is root on the VM, so a container escape from a solver is a VM compromise. Fix: add the four flags in `run_submission` for both containers (the referee needs the output bind, nothing else); in production, run the worker on a separate host or behind a Docker socket proxy that allows only `containers`, `images`, `networks`. Effort: under 1 hour for the flags; days for the socket proxy. |
| 4.2 | Low | **Output channel is validated.** The referee accepts only `{"scores": [floats]}` of the chunk's length, replaces non-finite values by 0, and scores a bad chunk 0 (`referee.py:score_split`). The only other player output is the HTTP 500 error text (500 chars) that ends up in `trace.jsonl`. A solver cannot write files the host reads. The player sees holdout features without labels; it could memorise them but has nowhere to send them. No change. |
| 4.3 | High | **Agent-written code runs on the host, outside the sandbox.** `serving/score.py:fitted_model` does `importlib ... exec_module` on `submission.py` and pickles the fitted model to `.cache/serving/`; `fraud/service.py:score_window` (today's queue), `models_registry/lists.py` and `value/scores._refit` call it with `submission_path(project_id, solver)`, which points at `workspace/<pid>/agent_solver/attempt_N/submission.py` for the LLM-written attempts. The AST screen (`agent_solver.screen_code`) blocks `os`, `subprocess`, `open`, `__import__` and a few dunders, which a motivated model output can still get around (`getattr(__builtins__, ...)` style access is not caught). Chain miners' code is not loaded on the host today (`submission_path` returns `None` for `miner-*` names, so a promoted miner version makes the queue fail with a missing file; a bug, see 4.4), but the obvious fix of passing `code_path` would make it Critical. The pickle cache is written and read by the app only. Fix: never exec outside code on the host. Score the queue through the player container (the referee already dumps `scores_<split>.csv`; add a `recent` split so the sandbox scores today's rows), or restrict promotion to built-in solvers. Effort: a few hours. |
| 4.4 | Medium | **A promoted outside solver breaks the queue and lists.** See 4.3: `score_window` raises `FileNotFoundError` for a `miner-*` solver. Fix together with 4.3. Effort: included above. |
| 4.5 | Low | **Apex screening list is narrower than the local screen.** `spec.yaml` forbids `socket, subprocess, requests, urllib, http` on top of the platform's base set; the local screen also blocks `os, sys, shutil, pathlib, importlib, ctypes, multiprocessing, pickle`. Inside the sandbox none of these reach anything secret, so this is defence in depth. Fix: align the two lists in v0.2.0. Effort: under 1 hour. |

### 5. Scoring integrity

| # | Severity | Finding |
|---|---|---|
| 5.1 | High | **A constant submission scores 94% of the bar.** Under `fraud_amount_per_day`, ranking by `score x (amount + fee)` with a constant score is "review the largest payments", which scores $3,724/day against v2's $3,961/day (`HANDOFF.md` §5 item 9, measured). Solvers compete in a 6% band; the takeover rule (+1% of the top) means a real model gains little over a trivial one, and the number tells the customer nothing about model quality. Fix: v0.2.0 scores **lift inside capacity**: `raw_score = (caught_model - caught_amount_only) / (caught_oracle - caught_amount_only)`, averaged per day, where `caught_oracle` ranks by `label x amount` (the most fraud money reviewable in `capacity` cases) and `caught_amount_only` ranks by amount. 0 means "no better than reviewing the largest payments", 1 means "caught everything catchable"; a constant submission scores 0 and cannot lead; money per day stays in metadata for the customer. `baseline_raw_score` becomes v2's lift, and the takeover bar is the platform's 1% of the top lift. Any change bumps `version` to 0.2.0 and is noted on issue #47; v0.1.0 is never edited. Effort: a few hours (metric, referee, generator, HANDOFF, tests). Implemented in Phase 2. |
| 5.2 | Medium | **Promotion gates are not in the referee.** Apex decides the winner on `raw_scores[0]` and the 1% rule; Concours promotes only after five gates (`fraud/gates.py`). A solver can win emissions on Apex and still not become the customer's model (a segment regression, or a slow model). That is correct for the customer but should be stated in the miner README and HANDOFF so nobody feels cheated. The speed gate could move into the referee (it already measures `seconds_per_10k`); the luck and segment gates need the champion's scores and cannot. Fix: README and HANDOFF wording in v0.2.0; speed gate enforced in the referee (score 0 when over the limit). Effort: under 1 hour. |
| 5.3 | Low | **Determinism.** `SEED` reaches `np.random.seed` in the player; LightGBM with `n_jobs=2` is deterministic for a fixed dataset and seed; the referee is stateless and the holdout fixed, so repeated runs agree (verified: cached replays match). The public leaderboard slice gives solvers 7 days of feedback; Apex limits probing by round length (2 days) and reveal delay. No change. |
| 5.4 | Low | **Leaderboard probing within Concours.** Locally there is no submission limit, but the only submitters are the built-in solvers, the agent (3 attempts) and chain miners (one round at a time). No change for the demo. |

### 6. Web app

| # | Severity | Finding |
|---|---|---|
| 6.1 | High (demo) | **The web app listens on all interfaces.** `scripts/dev.sh` runs `pnpm dev --port 3000` and `.claude/launch.json` the same; Next.js binds `0.0.0.0` by default, and `lsof` on this machine shows `node ... *:3000`. The backend binds `127.0.0.1:8000`, but Next rewrites `/api/*` to it (`next.config.ts`), so the API is reachable through the app. With 1.2, a venue guest signs in as the owner. Without 1.2 they can still hammer `/auth/login` (throttle is 10 per 5 min per IP, in memory) and load the pages. Fix: `pnpm dev -H 127.0.0.1` in `dev.sh` and `launch.json`; for a demo on a projector, that is all the demo needs. Effort: under 1 hour. Fixed in Phase 2. |
| 6.2 | Low | **Authentication is sound.** scrypt with per-user salt, random session tokens stored as SHA-256, HttpOnly + SameSite=Lax cookies (Secure in production, enforced by `production_checks`), API keys shown once and stored hashed, invites single-use and expiring, org scoping on every project read (`get_project`). `CONCOURS_SIGNUP=first` means the first account on an empty database becomes owner; on a freshly reset demo database, a Wi-Fi guest who is faster than the seed would own it. Fix: seed before enabling the network, or set `CONCOURS_SIGNUP=invite` after seeding. Effort: under 1 hour. |
| 6.3 | Low | **CORS** allows `localhost:3000` and `127.0.0.1:3000` with credentials in dev and the production domain only in prod (`config.ALLOWED_ORIGINS`). Fine. |
| 6.4 | Low | **Upload validation**: size is capped at 200 MB while streaming (`main.py:upload_data`); content type is not checked and the file is parsed by pandas, which is the intended behaviour for a CSV product. The error path leaks pandas text (2.6). A malformed 200 MB file costs tens of seconds of CPU. Fix: reject non-text content in the first 4 KB; keep the size cap. Effort: under 1 hour. |
| 6.5 | Low | **Path traversal**: project IDs come from the database (`get_project` first), so `project_dir(project_id)` never sees a user string; `transaction_id` from the URL is only stored. `/package/file` resolves the path and checks `str(p).startswith(str(comp))` without a trailing separator (`main.py:741`), so a sibling directory named `competition-x` would pass; none exists. Fix: `p.is_relative_to(comp)`. Effort: under 1 hour. |
| 6.6 | Low | **Zip-slip**: the app never extracts zips (`handoff/build.py` only writes them). Not applicable. |
| 6.7 | High | **CSV formula injection in exports.** `fraud/service.py:queue_csv` writes `transaction_id` (a value from the customer's file) and reason text into the download; `models_registry/lists.py` writes the uploaded rows back out with scores. A cell such as `=HYPERLINK("http://evil","click")` or `-2+3|cmd` is executed or evaluated when an analyst opens the file in Excel. Reproduced: `workspace/audit/messy.csv` row 1 has such an ID and it would reach the queue CSV unchanged. Fix: in both writers, prefix any cell that starts with `=`, `+`, `-`, `@`, tab or CR with a single quote (OWASP CSV injection guidance). Effort: under 1 hour. Fixed in Phase 2. |
| 6.8 | Medium | **SSE resource limits.** `/projects/{id}/arena/stream` polls the database every 0.5 s per open connection with no cap on connections per org or per project; the Improve page opens one per visit and the Protect page another. Fifty tabs is fifty pollers. Fix: cap streams per project (e.g. 10), back off polling to 2 s after 60 s idle, and close after 30 minutes. Effort: under 1 hour. |
| 6.9 | Low | **Security headers** are set by Caddy in production (HSTS, nosniff, DENY framing, referrer policy, `-Server`). The dev server has none, which is fine locally. |

### 7. Supply chain

| # | Severity | Finding |
|---|---|---|
| 7.1 | Low | **Lockfiles**: `backend/uv.lock` (`uv sync --frozen` in CI and the Dockerfile), `frontend/pnpm-lock.yaml` (`--frozen-lockfile`), `subnet/uv.lock`. The Apex SDK is pinned to a commit (`49eb05e`). Good. |
| 7.2 | Medium | **Actions pinned by tag, not SHA.** `.github/workflows/ci.yml` and the competition's `release.yml` use `actions/checkout@v4`, `docker/login-action@v3`, `sigstore/cosign-installer@v3`, `astral-sh/setup-uv@v6`, `pnpm/action-setup@v4`, `actions/setup-node@v4`. A moved tag runs attacker code with `packages: write` and `id-token: write`, which is enough to push and sign a poisoned referee image under the trusted identity. `permissions` are set at workflow level in `release.yml` (write on contents, packages, id-token); `ci.yml` uses the default token permissions. Fix: pin every `uses:` to a full commit SHA with a version comment (Dependabot keeps them fresh), add `permissions: contents: read` to `ci.yml`, and split the pin job's `contents: write` from the build job. Effort: under 1 hour per workflow; the release workflow change ships with v0.2.0. |
| 7.3 | Medium | **Base images by tag.** `python:3.12-slim` (player, referee), `python:3.11-slim` and `node:22-slim` (deploy), `postgres:16-alpine`, `caddy:2-alpine`, `ghcr.io/astral-sh/uv:latest` in the root `docker-compose.yml` (dev only; the deploy Dockerfile pins `uv:0.8.17`). A tag can change under you between the local build and the release build, so the signed image is not the image you validated. Fix: pin `FROM` lines by digest (`python:3.12-slim@sha256:...`) in the player and referee Dockerfiles (v0.2.0) and in `deploy/`. Effort: under 1 hour. |
| 7.4 | High | **No cosign verification before an image runs locally.** The local arena builds images from the staged folder and never pulls; nothing on this machine has verified the GHCR images (cosign is not installed; `docs/APEX_ONBOARDING_DRAFT.md` records that step as not done). Plan B pulls the signed images, so it must verify them first: `cosign verify --certificate-identity <workflow URL> --certificate-oidc-issuer https://token.actions.githubusercontent.com ghcr.io/...@sha256:...`, and refuse to run on failure. Fix: install cosign, verify by digest in the Plan B script, pin the digests from `spec.yaml`. Effort: under 1 hour. Done in Phase 2. |
| 7.5 | Low | **pip-audit**: no known vulnerabilities in the backend environment (`uv run --with pip-audit pip-audit -l`, 2026-10-29). |
| 7.6 | Medium | **pnpm audit**: 4 advisories, all transitive through `next@15.5.28`: all four in `postcss@8.4.31` (two high: arbitrary file read and path traversal through `sourceMappingURL`; two moderate: XSS in stringified output and an incomplete fix of the file read). They affect the build tool and dev server, not the shipped page. Fix: bump `next` to the current 15.5 patch and run `pnpm audit --fix`; re-run `pnpm build`. Effort: under 1 hour. |
| 7.7 | Low | **Images are amd64 only.** `release.yml` runs `docker build` on `ubuntu-latest`, so the signed images are `linux/amd64`; this laptop is Apple Silicon. They run under Rosetta emulation, slower. Fix: `docker buildx build --platform linux/amd64,linux/arm64` in v0.2.0's release workflow (cosign signs the index). Effort: under 1 hour. |

### 8. Compliance posture

| # | Severity | Finding |
|---|---|---|
| 8.1 | Low | **Card numbers are not stored.** `fraud/schema.drop_card_columns` removes Luhn-valid columns before the canonical dataset is written; the raw upload that may contain them is encrypted at rest from the moment it lands (`secure_store.encrypt_in_place`) and deleted after the columns are confirmed (`fraud/service.confirm_schema`). The protected data, the images and the handoff never contain them. Risk left: the raw upload sits encrypted for the minutes between upload and confirmation, and in a mapped customer-ID column (2.2). This keeps Concours out of PCI DSS storage scope in practice; say so with the caveat. |
| 8.2 | Medium | **Retention and deletion.** `DELETE /projects/{id}` removes the database row and `workspace/<pid>/` (raw, canonical, protected, competition, queues, labels), but not: the Docker images `concours-player-<pid>` and `concours-referee-<pid>` (which contain the train split and the holdout), the `.cache/arena/<hash>/` copies of run logs and scores, the `.cache/serving/*.pkl` fitted models (which embed training statistics), analyst labels in `case_label` (deleted by cascade? no: `CaseLabelRow` is deleted only with the row's project via SQLModel default, which does not cascade), events (pruned after 2 days). Fix: delete the images, the cache entries for the project's data hash, and the label rows in `delete_project`; add a retention setting (days to keep raw and canonical data) and document it. Effort: a few hours. |
| 8.3 | Low | **Notes for data agreements.** State: data stays on the customer's instance (one VM, Docker Compose, Postgres); uploads and identifiers encrypted at rest with a customer-held key; solvers receive hashed IDs, features and labels for the training window only, inside a private competition; the hidden holdout leaves the instance only inside the referee image, held privately on GHCR and run by Macrocosmos; no card numbers are ever stored; analyst verdicts are labels, not personal data; retention per 8.2; processor terms with Macrocosmos cover the referee image. Add the timestamp rounding from 2.3 before any real data. |

## What was verified, how

- Git history: regex sweep of `git log --all -p` for key, token and password patterns; `git log --all --diff-filter=A --name-only` for data files; `git rev-list --objects --all` for blobs over 2 MB; `git ls-files` for env files.
- Dependencies: `uv run --with pip-audit pip-audit -l` (clean); `pnpm audit` (4 advisories, all via `next`).
- Competition repo: `apex-dev preflight` and `apex-dev screen` pass on `/Users/parry/concours-fraud-repo` at `dab9c38`; `gh api user/packages` shows both packages private with a `v0.1.0` tag and a cosign `.sig` tag; `docker history` of the local referee image shows the `/app/data/` layer.
- Listening ports: `lsof` shows the Next dev server on `*:3000` and uvicorn on `127.0.0.1:8000`.
- Tests: 142 backend tests pass; `pnpm test` (copy lint and type check) passes, before any change.
- Not done: gitleaks and trufflehog are not installed on this Mac and `brew` is blocked by the Xcode licence; cosign is installed in Phase 2 for Plan B.

## Status after Phase 2 (2026-10-29)

Fixed on branch `claude/audit-and-demo-fallback`, one commit each:

| Finding | Commit | What landed |
|---|---|---|
| 1.2, 6.1 demo password and all-interfaces bind | `Security: bind the dev app to this machine and stop committing the demo password` | dev server on 127.0.0.1; seed generates a password into the gitignored `.env`; `.env.example` blank |
| 6.7 CSV formula injection | `Security: Excel-safe CSV exports` | `shared/csv_safe.py`, applied to the queue CSV, lists and scored files; tests |
| 4.1 container hardening | `Security: harden the arena containers` | cap_drop ALL, no-new-privileges, read-only root with noexec tmpfs, pid limits on both containers; verified with a fresh run |
| 4.3, 4.4 outside code on the host | `Security: outside solver code never runs on the host` | serving imports built-in solvers only; agent and chain code is scored by the player container through `referee/score_rows.py`; plain-English reasons without a model; pickle cache race fixed |
| 7.4 cosign before local runs | `Plan B: Apex-compatible local run ...` | `scripts/apex_local_run.sh verify` refuses to run unverified images; both v0.1.0 signatures verified on this machine |
| 3.3, 5.1, 5.2 scoring and result hygiene | `Competition v0.2.0: lift scoring, lean result metadata, plan C workflow` | lift metric, private number only in `raw_scores`, README states promotion is separate; v0.1.0 untouched; note drafted in `docs/ISSUE_47_UPDATE.md` |
| 7.2, 7.3, 7.7 pins and multi-arch | `Supply chain: pin Actions by commit SHA and base images by digest, least-privilege workflows` | ci.yml and release.yml pinned; base images by digest; buildx amd64+arm64 in the v0.2.0 release workflow |

Still open (Medium and Low, listed above): 1.3 (read-only PAT for the demo laptop; `docker login ghcr.io` on this
machine used the `gh` token, which is broader), 1.5, 2.2 keyed hashing and salt storage, 2.3 timestamp rounding,
2.4, 2.5, 2.6, 3.1(b) encrypted holdout in the repo, 3.4, 4.5, 6.2, 6.4, 6.5, 6.8 SSE limits, 7.6 `next` bump
for the postcss advisories, 8.2 deletion of images and caches with a project.
