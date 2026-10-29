# Apex onboarding: drafts (not sent)

Drafts for filing the sample-data fraud competition (`concours_fraud_6974713c0ea7`, project `6974713c0ea7`) with
Macrocosmos. Nothing here has been sent, pushed or opened. The repo name `parry22/concours-fraud` is a proposal;
if you pick another, set `CONCOURS_GITHUB_REPO` to it and rebuild the package so `spec.yaml`, `HANDOFF.md` and
`ONBOARDING_ISSUE.md` agree.

## 0. Decided: the starting bar is today's model

The adversarial set (HANDOFF.md §5 item 9, run through the local referee on 2026-10-28) scored:

| Submission | Private holdout | Share of v1 ($3,714/day) | Share of v2, the bar ($3,961/day) |
|---|---|---|---|
| constant (0.5 for every payment) | $3,724/day | 100.3% | 94.0% |
| random (uniform, seed 0) | $2,751/day | 74.1% | 69.5% |
| all zeros | $130/day | 3.5% | 3.3% |

Under `fraud_amount_per_day` a constant score ranks each day's payments by amount alone, so "review the 200
largest payments" already matches v1 (logistic regression). With `baseline_raw_score: 0` it would have led an
empty round.

Decision: `spec.yaml` now sets `defaults.baseline_raw_score` to the active model's private holdout score
(v2, lgbm_tuned, 3960.6343). The customer gains nothing from a result below the model it already runs, and this
matches Concours's own promotion rule. All three degenerate submissions sit below that bar, and taking the lead
needs the bar plus 1%. The metric itself is unchanged, so Concours's versions and gates still compare like for
like. `baseline_score` stays 0 because `apex-dev screen` treats it as a normalized score and flags 1.0 or more.

Rejected alternatives: scoring lift over the amount-only rule (changes the metric and breaks comparison with
v1/v2), and a bar at v1 (the constant clears it).

Still open, for Macrocosmos: their scoring service is not public, so the issue and email ask them to confirm that
`baseline_raw_score` sets the takeover bar for a raw-scale, spec-driven competition. If it does not, the fallback
is to seed the round with today's model as the first submission.

## 1. Checklist

**Status 2026-10-28:** steps 1 to 7 are done. `parry22/concours-fraud` is private on `main`, `v0.1.0` is tagged,
release run 40692555248 passed, `dab9c38` pinned both digests, and both GHCR packages are private, linked to the
repo, and carry a cosign `.sig`. Not done: `cosign verify` against the identity (cosign is not installed here),
steps 8 to 10.

Update: step 9 done (issue https://github.com/macrocosm-os/apex-competitions-builder/issues/47, the
`competition-onboarding` label needs a maintainer) and step 10 done (email sent by the owner). Step 8 waits on the
GitHub account Macrocosmos names.

Steps 2 to 5 are already done locally for the sample project with `parry22/concours-fraud` and the contact left
as TODO: the export is committed on `main` in `/Users/parry/concours-fraud-repo` (not pushed). From there, after
step 1: `gh repo create parry22/concours-fraud --private --source . --push`, then step 6. Redo steps 2 to 5 if
you change the repo name or want your name and email in HANDOFF.md.

1. `gh auth login` (the stored token for `parry22` is invalid), then `gh auth status`.
2. Set the owner settings in `backend/.env` and rebuild the package on the Launch tab (or `concours package`):
   `CONCOURS_GITHUB_REPO=parry22/concours-fraud`, `CONCOURS_OWNER_NAME=...`, `CONCOURS_OWNER_EMAIL=...`.
3. Export the repo contents: `concours package --repo repo.zip` (or `GET /projects/6974713c0ea7/package/repo`).
   This zip holds the private holdout. The handoff zip (`--out`) does not and cannot build the referee image.
4. Create the repo as **private**: `gh repo create parry22/concours-fraud --private`.
5. Push the export to `main` (unzip into an empty folder, `git init -b main`, add, commit, add the remote, push).
   `release.yml`'s pin job commits to `main`, so the default branch must be `main`.
6. Tag and push: `git tag v0.1.0 && git push origin v0.1.0`. Watch the `release` workflow in the Actions tab.
7. Confirm the pin: after the run, `main` has a "Pin image digests for v0.1.0" commit and `spec.yaml` holds two
   `sha256:` digests that are not the local build ids. Check them with
   `docker buildx imagetools inspect ghcr.io/parry22/concours-fraud-player:v0.1.0` (same for `-referee`), and
   check the signatures with `cosign verify` using the identity and issuer from `spec.yaml`. Note the tag points at
   the commit before the pin, so give Macrocosmos the pinned `spec.yaml` from `main`.
8. On GitHub, open both packages (`concours-fraud-player`, `concours-fraud-referee`) under your profile's
   Packages: confirm visibility is **Private**, and under Manage access add the GitHub account Macrocosmos names
   with read access. Add the same account to the repo as a read collaborator. The referee package carries the
   holdout; never make it public.
9. Paste the two digests into the issue body below (Image digest, Referee image digest), tick the last two
   pre-submission checks, and file the issue on `macrocosm-os/apex-competitions-builder` with the
   "competition onboarding" template.
10. Send the email in section 3.

## 2. Onboarding issue body

Template: `.github/ISSUE_TEMPLATE/competition-onboarding.yml` on `macrocosm-os/apex-competitions-builder`.
Generated by Concours with `CONCOURS_GITHUB_REPO=parry22/concours-fraud`; the two digests come from step 7.

Title: [onboarding] concours_fraud_6974713c0ea7 v0.1.0

### What is the competition?

Score each payment's chance of fraud (target `is_fraud`). Every day the 200 payments with the highest expected loss (score x amount) go to the fraud team; the more fraud money inside those cases, the better. Solvers submit a Python `submission.py` that trains on the public split and scores hidden rows. `raw_score` is Fraud amount caught per day within review capacity (capacity=200, fee=0.0, review_cost=10.0) on the private holdout, higher is better.

Success statement: A daily review queue that holds more fraud money than today's model, day after day, including after fraudsters change tactics, without dropping any amount band or new customers.

Starting bar: `defaults.baseline_raw_score` is 3960.6343, the model the customer runs today (v2 (lgbm_tuned), $3,961/day). A constant score already reaches 94.0% of it under this metric (it amounts to reviewing the largest payments), so the bar must hold from round one. Please confirm `baseline_raw_score` sets the takeover bar for a raw-scale, spec-driven competition; if it does not, how should the bar be seeded?

### HANDOFF.md

See `HANDOFF.md` in the repo at the released tag.

### Evaluation time budget vs. timeouts

Worst case: startup and training (measured 95 s locally) + 41 batches × 60 s deadline + scoring ≈ 2585 s.
`referee.timeout_s` = 5170, `evaluate.timeout_s` = 5170. Fits: yes.

### Competition id

concours_fraud_6974713c0ea7

### Spec version

0.1.0

### Competition repo URL

https://github.com/parry22/concours-fraud (private; Macrocosmos needs read access to the repo and its GHCR packages)

### Released git tag

v0.1.0

### Image ref (no tag)

ghcr.io/parry22/concours-fraud-player

### Image digest

sha256:cc491c83abbb715b9c476d4c7d31001ca55bb1d32f0e7d3978e5f8edbcbecd4c

### Referee image digest

sha256:06ea0c3288487ca4bd191d8ef617118e6ece96e6e14a6d6df39be1dae1f83822

### spec.yaml

See `spec.yaml` on `main` at `dab9c38` ("Pin image digests for v0.1.0", written by the release workflow).

### Pre-submission checks

- [x] `apex-dev preflight --spec ./spec.yaml --input fixtures/input.json` passes (pass)
- [x] local referee-driven run produced a valid result.json (pass; `apex-dev run` is not implemented upstream, Concours's harness follows the same contract)
- [x] The image is cosign keyless-signed by the repo's release workflow on the released tag (run 40692555248)
- [x] The image is pushed and pullable by digest (private GHCR packages; read access granted to the account you name)

## 3. Email to hello@macrocosmos.ai

Subject: Activating a fraud-detection competition on Apex stage or testnet for a buildathon demo

Hi Macrocosmos team,

I've filed an onboarding issue on apex-competitions-builder for `concours_fraud_6974713c0ea7` (v0.1.0): a
payment-fraud competition where solvers submit a `submission.py`, and a gym_v1 referee scores the fraud amount
caught per day inside a fixed review capacity on a private holdout. The spec passes `apex-dev preflight` and
`apex-dev screen`, the images are built and cosign-signed by the repo's release workflow, and a local two-container
run produces a valid `result.json`.

I'm demoing it at a buildathon and would like to run it end to end. Could you activate it on stage, or on Apex
testnet (netuid 61 on Bittensor testnet), for the demo? The repo and both GHCR packages are private because the
referee image holds the hidden holdout. Which GitHub account should I give read access to?

One scoring question: `defaults.baseline_raw_score` is set to the customer's current model (3960.6343),
because a constant submission already reaches 94% of it under this metric. Does that value set the takeover
bar for a raw-scale, spec-driven competition? If not, how would you like the bar seeded?

Issue: https://github.com/macrocosm-os/apex-competitions-builder/issues/47

Thanks,
<your name>
