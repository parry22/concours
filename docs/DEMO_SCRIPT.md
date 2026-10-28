# Demo script (3 minutes)

Before the demo: `./scripts/demo.sh` (reseeds the three projects; arena results replay from the cache), then
`./scripts/dev.sh`, open http://localhost:3000. Keep Docker Desktop running. Wi-Fi is not needed: intake
replays cached replies when `ANTHROPIC_API_KEY` is missing or `CONCOURS_OFFLINE=1`. Live replies come from
your Claude subscription through the Claude Code CLI (`claude auth login` once) or from `ANTHROPIC_API_KEY`
in `backend/.env`.

The dashboard already shows three projects: "Card fraud review queue, Q4" (Improve, v2, improving), "Churn
call list, postpaid" (Your model, v1, healthy) and "Inbound leads, November" (Launch, ready to launch).

| Time | Screen | Say and click |
|---|---|---|
| 0:00 | Home, then Your data | "Priya is a fraud lead at a lender. She has a spreadsheet and no ML team." Click the Card fraud card. Your data opens: about 297,000 transactions, 9 columns, 0.88% fraud, 10-row preview. Click The goal. |
| 0:30 | The goal | Tap the suggested reply "We want to catch more card fraud without annoying good customers.", then the next two: "About 1 in 1000 false alarms is fine." and "A missed fraud costs about 120 dollars, a blocked customer about 4. 300,000 transactions a month." The scoring rule ticks 4/4 with a one-line why. Click Confirm and protect. |
| 1:00 | Protect the data | Protection runs on arrival. The big red card: TX_FRAUD_SCENARIO, "This column would let a model cheat: it is only filled in after the outcome is known." Removed. The wow moment; pause. |
| 1:20 | Protect the data, then Your model | Under the card: "Building your first model", then "Your model v1 is ready." (22% of fraud caught at 1 false alarm per 1,000). Click Open your model, then the Fraud review queue: Score recent rows. Today's review queue: top 200 of 2,000, ranked, with the action column. Download the CSV. "Value on day one, before any contest." |
| 1:50 | Improve | Click Improve, then Run an improvement round. Attempts arrive as bars; the moment: "New model v2 promoted", 22% to 30% since your first model. The business number climbs; the raw score stays small. Money per month below. |
| 2:30 | Projects | Click All projects. Open "Churn call list, postpaid": v1, healthy, the churn call list. Same flow, different problem: "Leavers reached in your top 10%: 64%." Performance watch: Check with recent rows reads healthy. |
| 2:50 | Launch | Open "Inbound leads, November", Launch. Ready to launch 3/3. The improvement plan (illustrative), the terms, Download handoff. "Packaged to keep improving on Apex." Close on the one-liner: "A working model today. A global network of solvers keeps improving it." |

What to say if asked:
- "Did a live competition run?" No. The attempts are local solvers and are labelled "Local solvers (demo)".
  The package targets the Apex format and passes the toolkit's validation; launching goes through
  Macrocosmos' onboarding issue, which the handoff zip prefills.
- "Where is the private data?" Only inside the referee image on this laptop. The zip excludes it and carries
  its checksums.
- "Why these numbers?" Every number on screen is computed in code; the language model only asks questions
  and writes short explanations.
- "What does the customer pay?" An illustrative subscription plus a success fee on the measured improvement
  over their first model. The contest reward is an internal figure that goes to Macrocosmos in HANDOFF.md.
- "Why is the leads project on v2, not v3?" Ten solver variants were tried on that data; none clears the
  1% promotion margin over v2. A third version would need a number not produced by code.
