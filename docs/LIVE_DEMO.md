# Live demo prep (2026-10-31)

Everything here was run on the hosted copy on 2026-10-31 with the demo file; the numbers are what it printed.
`docs/JUDGE_DAY.md` stays the runbook for the laptop fallback and the infrastructure.

## The file

`demo-data/brightpay_payments_2018H1.csv` (7.8 MB, not in git; rebuild with
`backend/.venv/bin/python scripts/demo_csv.py`). "Brightpay" is a made-up card issuer.

| | |
|---|---|
| Rows | 61,823 card payments, 2018-04-01 to 2018-09-30 (six months) |
| Fraud | 496 payments, 0.80% |
| People | 174 customers, 6,630 merchants |
| Columns | payment_id, created_at, amount_usd, currency, customer_id, customer_email, card_number, merchant_id, channel, vendor_risk_score, chargeback_status, is_fraud |

Each column is there to make one point on screen:

- **card_number**: real-looking card numbers (Luhn-valid, one per customer). Protect removes them outright.
- **customer_email**: personal data. Replaced by one-way hashes.
- **chargeback_status**: only filled in after fraud is known. Protect catches it as a leak and drops it.
- **vendor_risk_score**: the customer's current fraud tool. Protect measures it, and every version is compared with it.
- **customer_id, merchant_id**: scrambled with a key that never leaves the machine.

Do not open it in Excel and save: Excel turns the card numbers into `4.09E+15`. Opening it to show is fine; upload
the original `.csv`. The hosted copy rejects uploads over about 10 MB (GitHub's port forwarding answers 413), so do
not swap in a bigger file.

Measured on the hosted copy with a 20-case queue:

| Step | Time | Result |
|---|---|---|
| Upload | 4 s | 61,823 rows, 12 columns |
| Match columns | instant | all 9 fields suggested by name, including the current tool's score |
| Protect | 1 s | card numbers removed, emails hashed, chargeback_status dropped, currency dropped (constant), 95 frauds not yet confirmed at training time, 30-day gap |
| Current tool | | $383 of fraud caught per day |
| v1 | about 2 min (cold Docker, not cached for a new upload) | $413 per day |
| Outside submission (velocity solver) | 6 s | $440 per day, all five gates pass, becomes v2 |

## Before you go on

1. `scripts/hosted.sh status` says Available and `(public)`. If not: `scripts/hosted.sh wake`.
2. `scripts/hosted.sh keepalive` running in a terminal (it stops when the terminal or the app closes).
3. Browser, three tabs, signed in as `demo@concours.local`:
   - Tab 1: the website, https://concours-demo-49wqv46v5pghxqr-3000.app.github.dev
   - Tab 2: the app on the projects list (`/app`)
   - Tab 3: "Card fraud review queue, Q4", Overview (v2, $3,961 a day, not yet jumped forward)
4. Terminal ready in the repo with the solver command typed but not run (the key goes in live):

   ```bash
   concours solve submit backend/solvers/lgbm_velocity/submission.py --url https://concours-demo-49wqv46v5pghxqr-3000.app.github.dev/api --key sk_PASTE
   ```

5. The CSV on the Desktop or in Finder, ready to drag.
6. Laptop fallback if the network dies: `./scripts/dev.sh`, http://localhost:3000, same login (docs/JUDGE_DAY.md).

## Talk track (about 4 minutes)

**0:00 Website (tab 1).** "Fintechs lose money to fraud every day. Most have analysts reviewing payments, few have
an ML team. Rules go stale in weeks, vendor scores are black boxes. Concours gives them a working fraud model on day
one from their own data, then a network of outside solvers keeps improving it, and a new version only goes live when
it proves it is better." Click **Sign in**.

**0:20 Upload (tab 2).** "This is Brightpay, a card issuer. Six months of payments, straight out of their database,
card numbers and all." **New project**, name it "Brightpay cards", **Start with your transactions**, drop the CSV.
"Every column is matched by name: ID, time, amount, customer, merchant, the fraud label, even the score from their
current vendor." **Confirm columns**.

**0:45 Three questions.** Type **20 cases a day** (one analyst), tap **About 10 per review, no extra fee**, tap
**Usually about 30 days**. "We measure models in money: fraud caught per day inside the queue the team can actually
review."

**1:00 Protect.** Read the red cards: "Card numbers: removed, nobody ever sees them. Emails: hashed. And this one,
chargeback_status, would let a model cheat: it is only filled in after the fraud is confirmed, so it is dropped."
Then: "Customer and merchant IDs are scrambled with a key that stays here. 95 frauds were not yet confirmed at
training time, so the model learns them as unknown, and a 30-day gap separates training from the test days. Their
current tool catches **$383 a day**; every version is compared with that." v1 starts building (about 2 minutes).

**1:30 While v1 builds: Improve (tab 3, Q4 project).** "This customer has been on Concours for a quarter. v1, then
v2 from an improvement round." Open **Improve**: "Each attempt is measured on hidden days it never saw, and must
pass five gates: hidden data, same rows, a luck test that resamples the days a thousand times, no segment worse by
more than 5%, and practical to run." Point at the signed-image runs: "These four were scored with our signed Apex
competition images, the same referee and player containers Apex runs."

**2:10 Jump forward (tab 3).** Overview, **Jump forward 4 weeks**. "Fraudsters change: card testing, then cash-outs
at terminals the cardholder never used. Health turns red, a round starts on its own." (Takes about 40 s.) "No model
trained on old labels can know this pattern. The velocity attempt passes all five gates and becomes **v3: $6,543 a
day** against $4,840 for the model it replaced."

**2:50 Back to Brightpay (tab 2).** v1 is ready: "**$413 a day** against **$383** for their vendor, on day one."
Open **Review queue**: "Today's 20 payments ranked by expected loss, three plain-English reasons each." Mark the
first one **Fraud**: "That verdict is a new label; the next round learns from it."

**3:15 Outside solver, live.** On **Improve**, under **Outside solvers**, create a key ("Judge"), copy it, paste it
in the terminal command, run it. "This is the door any outside solver uses: download the kit with the bar, write a
submission, send it. Scored in a sandbox on the private holdout, through the same five gates." It lands in about 6 s:
"**$440 a day**, all five gates pass, it is now **v2**, credited to the solver." Refresh Improve to show it.

**3:40 Close.** "On Bittensor: the competition is packaged for Apex, subnet 1, signed v0.2.0 images, filed with
Macrocosmos. And we run the same loop as our own testnet subnet, netuid 603: a miner committed its code hash on
chain, Concours validated it, it became a version credited to that miner, and weights were set on chain. Fraud
models that keep up with fraudsters."

If v1 is not ready at 2:50, do the outside-solver step on the Q4 project instead and come back to Brightpay last.

## Questions you will get

- **Which track?** Build on a Subnet: we extend Apex (SN1) with a new competition type, a customer-facing one, and
  run our own testnet subnet (netuid 603) with Concours as the validator.
- **Is it live on Apex?** No, never say it is. "The competition is filed and the package is signed. Macrocosmos has
  not activated it yet, so we ran the signed Apex images ourselves; the scores match the filed numbers. The same loop
  runs live on our testnet subnet."
- **Is the subnet real?** Testnet, netuid 603. Subnet registered at block 8335051, miner uid 1's velocity solver
  became v2 ($6,543 vs $4,685 a day), weights set to uid 1 at block 8335151 through commit-reveal.
- **Why would miners do this?** The customer pays a subscription plus a success fee on measured improvement over
  v1 (the illustrative plan on the Launch screen). On the subnet, the solver whose code becomes the customer's model
  gets the weights, so emissions go to whoever actually improved it. The gates make gaming expensive: a lucky day
  fails the luck test.
- **Who sees the customer's data?** Solvers get scrambled IDs, no card numbers, no emails, no leak columns, and never
  the hidden test days. They can tell two payments share a customer, never who it is.
- **Real-time?** No. A daily batch queue sized to the analysts. Checkout scoring is out of scope.
- **How do you score when fraud is confirmed weeks later?** Training only uses labels known at the cutoff, a gap
  separates training from testing, and the test days are old enough for their labels to have matured.
- **Is the data real?** Simulated: the Fraud Detection Handbook's transaction simulator (ULB Machine Learning
  Group), renamed to look like a real export. Same patterns real fraud teams see: big-amount fraud, compromised
  terminals, compromised cards.
- **Was that outside submission really outside?** It is our velocity solver, sent through the public solver path
  with a solver key, exactly as an outside solver would. Anyone with a key can do the same.
- **Why not promote on the average?** One lucky day can make an average. The luck test resamples the days 1,000
  times and needs a win in 95% of them.
- **Do customers own the models?** Yes: every promoted version and its code.

## Never say

- "Live on Apex" or "running on mainnet".
- Numbers that are not on screen. Every figure above came from the product.
