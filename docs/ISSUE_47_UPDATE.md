# Draft update for issue #47 (not posted)

For the founder to review and paste as a comment on
[macrocosm-os/apex-competitions-builder#47](https://github.com/macrocosm-os/apex-competitions-builder/issues/47)
once v0.2.0 is tagged and the release workflow has pinned the new digests. Nothing below has been sent.
v0.1.0 is untouched: same tag, same images, same `spec.yaml`.

## Plain-English summary

The scoring rule of v0.1.0 lets a trivial submission ("review the 200 largest payments") score 94% of the bar,
so solvers had almost nothing to win. v0.2.0 scores how much of the *remaining* catchable fraud a solver finds
beyond that rule. A trivial submission now scores exactly 0, today's model scores 0.117, and the leader must beat
that by 1%. The data, the hidden rows and the player interface are unchanged; the referee reports both numbers.

## Comment text

---

Update: **v0.2.0** of `concours_fraud_6974713c0ea7` is tagged on `parry22/concours-fraud`. v0.1.0 stays as filed;
please activate 0.2.0 instead.

**What changed**

- **Scoring.** `raw_scores[0]` is now `fraud_lift_in_capacity`: every holdout day, the referee builds three
  200-case review queues (the solver's, ranked by score x amount; the "largest payments first" rule, a constant
  score; and the best possible queue, ranked by the true label) and reports
  `sum(solver - rule) / sum(best - rule)` pooled over days. 0 means no better than reviewing the largest payments,
  1 means every catchable payment was caught, negative means worse than the rule. The reason: under v0.1.0's
  money-per-day metric a constant submission scored 94.0% of the bar, so the band solvers competed in was 6%.
  Measured through the same referee on 2026-10-29: constant 0.0000, random -0.4827, all zeros -1.7829; today's
  model (v2, LightGBM) 0.1171 lift ($3,961/day). `defaults.baseline_raw_score` is therefore **0.1171**;
  `baseline_score` stays 0 (the screen reads it as normalized). The money per day of every queue is still in
  `details.json` and in the metadata summary, so the customer's own numbers are unchanged.
- **Result hygiene.** `result.json` metadata now carries only the public score, row counts and timings. The
  private number travels in `raw_scores` only; per-split detail goes to `/data/details.json`, which the owner
  reads. This keeps hidden results hidden if the dashboard shows metadata to miners.
- **Images.** Built for `linux/amd64` and `linux/arm64` (`buildx`), the index is what cosign signs and what
  `spec.yaml` pins. Base image pinned by digest. Actions pinned by commit SHA; the release workflow's jobs have
  split, least-privilege permissions.
- **Repository hygiene.** The holdout is committed encrypted from v0.2.0 on (`referee/data/*.enc`, decrypted in the
  release workflow from a repository secret); v0.1.0's commit still has it in clear in this repo's history.
- **README.** States that leading on Apex and being promoted to the customer's model are different things
  (Concours applies five gates on its side), and documents the lift formula.
- Unchanged: train split, hidden rows, labels, `input.schema.json`, player image contents, timeouts, resources.

**Open questions, as before**

1. Does `defaults.baseline_raw_score` set the takeover bar for a raw-scale, spec-driven competition? If not,
   how should the bar be seeded?
2. Which GitHub account needs read access? We will grant read on the two packages (`concours-fraud-player`,
   `concours-fraud-referee`) only; `spec.yaml` and `HANDOFF.md` are attached here.
3. Stage or testnet (netuid 61): whichever is faster for a short activation this week.

Digests (from `spec.yaml` on `main` after the pin commit): player `sha256:<fill after release>`,
referee `sha256:<fill after release>`.

---

## Checklist before posting

- [ ] In the competition repo, review branch `v0.2.0` (local clone `/Users/parry/concours-fraud-repo`), then
      `git checkout main && git merge v0.2.0 && git push origin main`.
- [ ] Add the repository secret `HOLDOUT_KEY` (Settings, Secrets and variables, Actions) with the output of
      `cd backend && .venv/bin/python -m app.handoff.build key 6974713c0ea7`. The release workflow needs it to decrypt
      `referee/data/*.enc`.
- [ ] `git tag v0.2.0 && git push origin v0.2.0`; wait for the `release` workflow; confirm the "Pin image digests for
      v0.2.0" commit on `main`.
- [ ] Paste the two digests into the comment above.
- [ ] Attach the new `spec.yaml` and `HANDOFF.md`.
- [ ] Post the comment; do not edit the original issue body.
