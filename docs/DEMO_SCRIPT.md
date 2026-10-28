# Demo script (3 minutes)

Before the demo: `./scripts/demo.sh` (seeds both templates so the arena replays instantly), then
`./scripts/dev.sh`, open http://localhost:3000. Keep Docker Desktop running. Wi-Fi is not needed:
intake replays cached replies when `ANTHROPIC_API_KEY` is missing or `BRIEF_OFFLINE=1`. Live replies come from
your Claude subscription through the Claude Code CLI (run `claude auth login` once in a terminal; no API
key needed) or from `ANTHROPIC_API_KEY` in `backend/.env`. To record real replies for the scripted path once,
log in, run `./scripts/demo.sh`, then set `BRIEF_OFFLINE=1` for the demo; without a key the deterministic default replies are used and the spec still
completes in three turns.

| Time | Screen | Say and click |
|---|---|---|
| 0:00 | Home | "Priya is a fraud lead at a lender. She has a spreadsheet and no ML team." Click the Fraud template. The dataset loads: about 297,000 transactions, 9 columns, 10-row preview. |
| 0:30 | Describe the goal | The goal sentence is prefilled: "We want to catch more card fraud without annoying good customers." Send. Answer the two questions: "About 1 in 1000 false alarms is fine." and "A missed fraud costs about 120 dollars, a blocked customer about 4. 300,000 transactions a month." The spec card fills: target TX_FRAUD, metric in plain words, why. Click Confirm spec. |
| 1:00 | Protect the data | Click Run protection. Split by time: 70 / 10 / 20. The big red card: TX_FRAUD_SCENARIO, "This column would let solvers cheat: it is only filled in after the outcome is known." Dropped. TRANSACTION_ID dropped as an identifier. Pause here. |
| 1:30 | Arena | Optional stretch: Add an agent solver. A model writes a solver from the schema alone, up to three attempts, each scored by the same referee. Takes about a minute per attempt live, replays instantly after `BRIEF_SEED_AGENT=1 ./scripts/demo.sh`. |
| 1:30 | Arena | Click Run local solvers. Rows animate in: baseline, lgbm default, lgbm tuned. The business card climbs: "Fraud caught at 1 false alarm per 1,000 good transactions: 22% to 30%." Click Finalize: private scores revealed, winner picked. Badge: Validate with Apex toolkit, pass. |
| 2:15 | Use the winner | Click Use sample rows (fresh rows from after the training period). Preview shows score and flag. Download scored CSV. |
| 2:35 | Header | Switch template to Churn. Same flow, different problem: confirm spec, protect (Status warned, duplicates removed), arena replays: "Of customers who left, reached by contacting your riskiest 10%: 47% to 64%." |
| 2:55 | Launch on Apex | Show the package tree and the illustrative pricing. Click Download handoff package. Close: "Every company has a prediction problem sitting in a spreadsheet. Brief puts it in front of Bittensor's global solvers and hands back a better model. Fraud is just where we start." |

What to say if asked:
- "Did a live competition run?" No. The solvers are local stand-ins and are labelled local. The package targets the Apex format and passes the toolkit's validation; launching goes through Macrocosmos' onboarding issue, which the handoff zip prefills.
- "Where is the private data?" Only inside the referee image on this laptop. The zip excludes it and carries its checksums.
- "Why these numbers?" Every number on screen is computed in code; the language model only asks questions and writes short explanations.
