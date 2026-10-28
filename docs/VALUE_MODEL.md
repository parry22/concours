# Value model

How Brief turns a leaderboard score into money. Replaces the single-line savings estimate
(`volume x positive rate x recall lift x cost per miss`) that shipped first.

## What changed

| Before | Now |
|---|---|
| Three hard-coded template numbers | Every parameter carries a source: `data` (measured from the file), `user` (given in intake or edited on the arena screen), or `default` (industry placeholder, labeled as such) |
| Recall lift only | Full confusion matrix at the operating point, scaled to a month: true positives, false positives, misses, and what each one costs or earns |
| One number | A 90% range from a bootstrap of the evaluation split, the "do nothing" exposure, and the value curve across every operating point |
| Fixed operating point | The contract point (the false-alarm budget or contact share agreed in intake) and the value-optimal point, side by side |
| No way to check assumptions | Sensitivity table (each parameter at half and one and a half times its value) and break-even values |

## Parameters

Common to every template:

| Key | Meaning | Default source |
|---|---|---|
| `rows_per_month` | Rows scored in a month | `data` when there is a time column (rows / months spanned), else the file is treated as one month and the source is `default` |
| `positive_rate` | Share of rows that are positives | `data`, measured on the whole file |
| `value_per_positive` | Money at stake per positive: the fraud amount, or the revenue kept when a leaver stays | `data` when an amount or value column exists (mean over positive rows), else `default` |
| `action_success_rate` | Share of flagged positives where the action works: fraud blocked before the loss, or a contacted customer who stays | `default` (fraud 1.0, churn 0.25) |
| `cost_per_action` | Cost of acting on any flagged row, right or wrong: a review, a call | `default` (fraud 0, churn 3) |
| `cost_per_false_positive` | Extra cost of a wrong flag: a declined good customer | `default` (fraud 4, churn 0) |

Intake stores only what the user gave, under `spec.economics`. The old keys `monthly_volume`,
`cost_fn`, `cost_fp` still work as aliases.

## Computation

For an evaluation split with labels `y` and solver scores `s`:

1. Operating point. Contract: threshold at the agreed false-positive rate (`recall_at_fpr`) or
   contact share (`recall_at_top_k`). Optimal: the threshold on the value curve with the highest net.
2. Confusion counts at that threshold, scaled by `rows_per_month / rows_in_split`.
3. Money per month:

   ```
   gross = TP x action_success_rate x value_per_positive
   costs = (TP + FP) x cost_per_action + FP x cost_per_false_positive
   net   = gross - costs
   ```

4. Exposure without a model: `positives_per_month x value_per_positive`.
5. Uplift: leader net minus baseline net at the contract point.
6. Range: at a fixed threshold every row falls into one of four cells, so a bootstrap of the rows is a
   multinomial draw over the cells. 1,000 draws, seed 0, 5th and 95th percentile of recall and net.
7. Curve: 80 operating points from 0.05% to 50% of rows flagged.
8. Sensitivity: net with each money or rate parameter at 0.5x and 1.5x. Break-even cost per false
   positive and break-even action success rate when they exist.

Before finalize the evaluation split is the public leaderboard slice and the threshold is chosen on
that same slice, so the numbers are mildly optimistic. After finalize the threshold is chosen on the
leaderboard slice and applied to the private holdout, which is the honest estimate.

## Where the scores come from

The referee writes `scores_leaderboard.csv` and `scores_holdout.csv` next to `result.json` in its
`/data` volume. They stay in `workspace/<project>/arena/<submission>/out/` and in `.cache/arena/`
and never enter the handoff zip. When a cached result predates this file (older runs), the value
model re-fits the solver locally through the serving path and writes the files for next time.

## Still illustrative

The defaults above are placeholders and are labeled as such in the UI. The pricing slider on the
launch screen is unchanged and still illustrative.
