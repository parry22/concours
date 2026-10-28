# Demo script (3 minutes)

Before the demo: `./scripts/demo.sh` (wipes the workspace, reseeds two fraud projects; arena runs and fitted
models replay from `.cache/`), then `./scripts/dev.sh`, open http://localhost:3000. Keep Docker Desktop
running. No network is needed: the three questions are parsed in code.

Rehearse once on a new machine: the first `demo.sh` runs every solver in Docker (about 10 minutes), and the
first jump forward runs the drift round in Docker (about 3 minutes). Every later run replays in seconds.

The dashboard shows two projects: "Card fraud review queue, Q4" (v2, Improving) and "Marketplace payments"
(v1, Slipping: drift injected, round ready to run).

| Time | Screen | Say and click |
|---|---|---|
| 0:00 | Home, then Your transactions | "Priya runs fraud operations at a payments company. Five analysts, no ML team." Click **Try with sample data**. 1.76 million payments load; the mapping screen has already matched TRANSACTION_ID, TX_DATETIME, TX_AMOUNT, CUSTOMER_ID, TX_FRAUD and TERMINAL_ID. Click **Confirm columns**. |
| 0:20 | Three questions | Tap the three suggestions: "200 cases a day", "About 10 per review, no extra fee", "Usually about 30 days". The settings panel fills in. Protection starts. |
| 0:35 | Protect the data | The red card: **TX_FRAUD_SCENARIO**, "This column would let a model cheat", removed. Under it: customer and merchant IDs scrambled, the clock counters removed, and "2,7xx frauds were not yet confirmed at training time", with a 30-day gap before the test days. "Solvers never see the hidden test data." |
| 1:00 | Overview, then Review queue | "Model v1 ready: $3,7xx of fraud caught per day in a 200-case queue." Net value per day after review costs. Open **Review queue**: today's 200 payments ranked by expected loss, with three reasons each ("Unusual amount", "Terminal had recent fraud"). Mark the first case **Fraud**: "That verdict is a new label; the next round learns from it." |
| 1:30 | Improve (Card fraud review queue, Q4) | Switch to the seeded Q4 project, Improve. The attempts with money per day first, and under each attempt the five gates. The promoted one: v2, "Wins in 100% of resamples", "No segment drops more than 5%". "Up from $3,7xx with your first model." |
| 2:10 | Overview, jump forward | Overview, **Jump forward 4 weeks**. Health turns red: "New fraud pattern detected. Your model is catching 2x% less fraud. Improvement round started." On Improve: the current model is re-scored on the new days, then the velocity attempt passes all five gates and becomes **v3**, catching the card-testing cash-outs. (If short on time, open "Marketplace payments", which is already slipping, and press Run an improvement round.) |
| 2:45 | Launch | Launch: what goes to Apex (spec, player and referee images, the queue metric, the gates and the embargo in HANDOFF.md), the illustrative improvement plan, the IP terms, Download handoff. Close: "Fraud models that keep up with fraudsters." |

Numbers marked `x` depend on the seed; every number on screen comes from code.

What to say if asked:
- "Is this real-time?" No. A daily queue sized to the team. Real-time scoring is out of scope.
- "Did a live competition run?" No. The attempts are local solvers, labelled "Local solvers (demo)". The
  package targets the Apex format and passes the toolkit's validation.
- "Where are the customer IDs?" Hashed with a key kept on this machine. Solvers can tell two payments share a
  customer, never who it is. Card numbers are removed outright.
- "How do you score when fraud is confirmed weeks later?" Training uses labels as known at the cutoff; a gap
  of 30 days separates training from the test days; the test days are the newest ones whose labels have
  matured. The sample has no confirmation dates, so they are simulated (7 to 60 days, the same every run).
- "Why not promote on the average?" One lucky day can make an average. The luck test resamples the days
  1,000 times and needs a win in 95% of them.
- "Why did v3 catch the new pattern?" The new pattern (card testing, then cash-outs at terminals the
  cardholder never used) does not exist in older data, so no model can learn it from labels yet. The winning
  attempt adds velocity features and two card-testing rules; the gates confirm it catches more fraud money
  without losing any segment.
