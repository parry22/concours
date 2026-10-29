# Concours customer journey audit

Date: 2026-10-29. Persona: Priya, fraud operations lead at a mid-size marketplace. Four analysts, no ML team.
Her acquirer warned her that Visa's monitoring program now flags merchants at a 1.5% fraud-and-dispute ratio
and fines per case. She has a CSV export of six months of payments with a chargeback flag and a fraud score
from her current tool. She wants fewer losses without hiring a data scientist.

Two walks on the dev build on this laptop (2026-10-29): once with the bundled sample (1.75 million simulated
payments), once with a deliberately messy file built from an 8% slice of the sample (renamed columns, three date
formats, currency symbols and thousands separators in amounts, 3% blank amounts, blank terminals, a constant
`notes` column, a `channel` column, two columns that leak the answer, a card-number column, and one transaction ID
that is an Excel formula).

## Summary for the founder

Time to first value with the sample is about four minutes and eleven clicks, with a cold Docker run; seconds
when the result is cached. That is excellent and is the demo. With a real file the journey breaks at the second
screen: Concours refuses dates in more than one format and amounts with currency symbols, tells the user the
column "does not read as numbers", and offers no way to fix it inside the product. Once the file is clean, the
protection step is the best part of the product (it caught both planted leak columns and explained them in plain
English), but a file whose newest weeks are sparse builds a model on almost nothing and then the queue page
crashes with "Something went wrong".

Against the market, Concours's genuine edge is that the model keeps improving on the customer's own data with a
promotion rule a non-engineer can understand, and that it tells the truth about what the model is tested on.
Every competitor the persona will have talked to (Stripe Radar, Sift, Kount, Forter, SEON, Sardine) has a review
queue with case status, rules next to the model, and dispute tracking; Concours has a queue with verdicts and
nothing else. For a week, the right moves are: make the upload survive a real CSV, show "versus your current
tool" and the Visa ratio so the first screen speaks the persona's language, add plain-English "what changed" to
each version, a trust page, a 5% exploration slice in the queue, Excel-safe exports, and a clear "local run"
label. Case management, rules, alerts and integrations are the next quarter.

## Walk 1: sample data

Clicks counted from the project switcher's "New project". Times on this laptop, first run (nothing cached).

| Step | What Priya wants | What happens | Friction | Severity | Fix | Effort |
|---|---|---|---|---|---|---|
| 1. New project (3 clicks: New project, name, "Try with sample data") | See the product work on something | Project opens on "Your transactions" after about 10 s with 1,754,155 payments and a 0.84% fraud rate; all five required fields plus terminal already matched, each with a sample value | No progress state during the 10 s (the modal button spins, nothing else); "3 other columns stay as extra features" includes `TX_FRAUD_SCENARIO`, which a careful user knows is a leak and will worry about until the next screen | Low | Show "Reading 1.75 million payments" in the modal; on the mapping screen, show the date range found ("183 days, 2018-04-01 to 2018-09-30"; the copy key `mapping.days` exists and is unused) | under 1 hour |
| 2. Confirm columns (1 click) | Move on | "Reading every row" for about 15 s, then "Three questions" | Fine | | | |
| 3. Three questions (3 clicks on the suggestion chips) | Give the numbers and move on | Chat-style, one question at a time; the panel on the right fills in; auto-advances to Protect | Three numeric facts asked as a chat is slower than a form; "Send an empty answer to keep the default" is odd; no "use all three defaults" | Medium | Keep the questions, add one button "Use these defaults" above the chat, and a form fallback (three inputs) on the right panel that writes the same settings | a few hours |
| 4. Protect the data (automatic) | Know her data is safe and see something | Checks animate for about 20 s; the red card "TX_FRAUD_SCENARIO. This column would let a model cheat" lands; below it "Building your first model" | Copy says "A few seconds when the data is known", but the cold build took about three minutes (two solvers in Docker) with no progress or estimate; nothing says Docker is working | High (demo) | Show the two attempts with a progress line ("Training model 1 of 2, about 2 minutes") from the live stream the Improve page already has; say "about 3 minutes the first time, seconds after" | a few hours |
| 5. v1 ready (0 clicks) | A number she can repeat to her boss | "Your model v1 is ready. $3,714 of fraud caught per day in a 200-case queue." | Excellent. Only miss: no comparison to what she has today | Medium | "versus your current tool" (see ideas) | a few hours |
| 6. Overview (1 click) | Understand the model | Hero number, daily bars, net value, precision, false alarms, health, versions | "Jump 4 weeks" is a simulation control on a production screen; for a real customer it is confusing ("will this change my data?"); health says "No week has mature labels since this model was built. Jump forward" | Medium | Show the jump button only for sample projects (or behind a "demo" flag); for real data, health reads "Checks start when the first week of labels matures (about 30 days)" | under 1 hour |
| 7. Review queue (1 click) | Hand analysts today's work | 200 cases ranked by expected loss, three reasons each, Fraud / Not fraud, CSV download; loads in about 8 s | No way to say who is reviewing what, no status beyond the verdict, no notes, no search, no sort, no filter by amount or reason, no ageing; "Customer" shows a hex hash the analyst cannot look up; reasons repeat the same three phrases | High | Case basics: assignee, status (open, reviewing, done), note, filters; keep the real transaction ID as the lookup key and say so ("look it up by transaction ID in your system"); a status column in the CSV | days |
| 8. Verdict (1 click) | Teach the model | Button toggles; "Verdicts are saved as new labels dated today" | Good. No undo confirmation needed | | | |
| 9. Improve (1 click) | See it get better | Attempts with money per day, five gates per attempt, "Local solvers (demo)" badge, run log | Jargon: "private holdout", "public check", "resamples"; the badge does not say what a local solver is; no estimate of how long a round takes; "Run an improvement round" on a healthy model has no stated reason to press it | Medium | Tooltips exist for some terms; add one line under the badge ("Attempts run on this machine, measured the same way Apex will"); show an ETA from the last run | under 1 hour |
| 10. Data (1 click) | Trust | Protection report, late-labels timeline | Good content, engineer-flavoured labels ("Public check", "Private holdout", "seed 42") | Low | A "What leaves this machine" box at the top (trust page) | a few hours |
| 11. Launch (1 click, then "Build and validate") | Understand the improvement plan | File tree of spec.yaml, Dockerfiles and YAML; validation steps; an "illustrative" subscription and success fee in dollars; terms | The file tree is for Macrocosmos, not for Priya; the plan looks like an invoice; nothing says whether a competition is running | High (honesty) | Move the file tree under "Technical details"; label the plan "Example pricing" in the card title; add the live-versus-local status line | under 1 hour |

Time to first value (v1 number on screen): about 4 minutes, 11 clicks, cold. About 1 minute when the arena
cache is warm. Time to first queue: about 4.5 minutes.

## Walk 2: a messy file

| Step | What Priya wants | What happens | Friction | Severity | Fix | Effort |
|---|---|---|---|---|---|---|
| 1. Upload `messy.csv` (11 MB, 140,332 rows) | See it load | 0.8 s; 12 columns profiled; preview shows the first rows including the formula cell as-is | Fine | | | |
| 2. Suggested mapping | Not have to think | `amt`, `fraud_flag`, `store`, `ccy` matched; `txn_ref`, `posted_at`, `cust` not matched; the picker shows sample values, which makes manual mapping easy | Three of five required fields unmatched because the name list misses `ref`, `posted`, `cust`, `created`, `date_time`; the badge "2 of 5 required matched" is clear | Medium | Add common patterns (`ref`, `reference`, `posted`, `cust`, `card`, `acct`, `txn_date`, `created`), and fall back to content: the column whose values parse as dates, the numeric column with the widest range | under 1 hour |
| 3. Confirm columns | Move on | 400: "posted_at does not read as dates and times. amt does not read as numbers." | Dead end. The message does not say why (three date formats; `$`, `€` and `1,234.50` in amounts) or what to do; there is no fix inside the product; Priya opens Excel | High | Parse amounts by stripping currency symbols, spaces and thousands separators; parse dates with `format="mixed"` and tell the user which formats were seen ("3 date formats found, read as day/month/year"); show the first five values that failed | a few hours |
| 4. Retry after cleaning dates and amounts | Move on | 400: "amt does not read as numbers." (3% blanks exceed the silent 1% tolerance) | Same dead end, second time | High | Blank amounts: drop the rows and say so ("4,206 payments had no amount and were left out") | under 1 hour (with step 3) |
| 5. Retry with blank rows removed | Move on | Confirmed in 1.2 s; three questions through the API; Protect in 1.6 s | | | | |
| 6. Protection report | Trust | Two red cards: `chargeback_amt` and `fraud_type` "would let solvers cheat: on its own it predicts the outcome almost perfectly"; `notes` dropped as constant; IDs scrambled; 197 frauds not yet confirmed at training time | Excellent. Gaps: `card_pan` was removed at confirmation and the report never mentions it (the "Card numbers removed" check shows while running but there is no finding line); `ccy` with `USD`, `usd`, `EUR` and blanks kept as a feature without normalisation; `channel` kept (fine) | Medium | Record the card-column drop as a finding; upper-case and trim currency codes | under 1 hour |
| 7. v1 built | A number | 40 s, "$188 of fraud caught per day" on this 8% slice | | | | |
| 8. Queue | Hand analysts work | HTTP 500, "Something went wrong on our side" | The file's newest weeks were sparse (a parsing mistake in my cleaning pushed a few hundred rows into December), so the public-check window held zero rows; protection and v1 went ahead anyway and the queue crashed when the model scored an empty frame | High | Before building anything, count the rows in each window and refuse with a sentence when the public check or the holdout has fewer than, say, 500 payments or the newest 30 days are under 1% of the file; show the four windows with their row counts on the mapping screen | a few hours |
| 9. Queue export | Open in Excel | Not reached on this project; on the sample project the CSV writes `transaction_id` verbatim, so `=HYPERLINK(...)` would be executed by Excel | Security finding 6.7 | High | Escape cells starting with `=`, `+`, `-`, `@` | under 1 hour (done in Phase 2) |

Time to first value with a real file: not reachable without leaving the product. Once the file is clean: 44 s to
v1 on 136,000 rows.

Missing states noticed on both walks: no empty state on Improve before any round ("2 local solvers ready" only);
no loading estimate anywhere a Docker run happens; no error state on Overview when the queue fails (the queue
page shows the generic 500 text); no "what next" when health is unknown on real data.

## Competitor landscape (verified 2026-10-29 by web search, see sources)

| Vendor | Model | What the persona gets | Relevance to Concours |
|---|---|---|---|
| Stripe Radar | bundled with Stripe payments; ML plus custom rules | Block/allow/review per payment, a review queue, lists, rules with priority order, benchmarks against similar businesses, a fraud workspace covering reviews, disputes, rules and risk controls | Sets the bar for "review queue plus rules plus dispute view in one place" and for benchmarks |
| Adyen RevenueProtect | bundled with Adyen | Risk rules and ML scoring, case management, dispute handling in the same dashboard | Same bar |
| Sift | scoring platform | Scores, workflows and queues, console with explanations ("signals"), rules | Case management and explanations are expected |
| Kount (Equifax) | scoring platform | Configurable policies and rules, device and identity trust scoring, case management | Rules alongside models are expected |
| Forter | decision platform with chargeback guarantee | Identity-based approve/decline decisions, chargeback liability on approved orders, evidence-driven alert triage | Guarantee is a different business model, not a feature to copy |
| SEON | scoring platform, SMB pricing | Published pricing from $699/month for 2,500 checks, device and email intelligence, rules, case management | The price anchor the persona will quote |
| Sardine | fraud and AML platform | Natural-language or no-code rules with backtests, shadow mode and A/B tests; case management with saved views, cross-queue actions, AI summaries, two-person review | The most modern reference for "rules you can test before you turn on" |
| Signifyd, Riskified | loss guarantee | Approve/decline with reimbursement of fraud chargebacks on approved orders (Signifyd within 48 hours, also non-fraud disputes; Riskified fraud chargebacks), about 0.8% of approved order value on a public listing | Guarantee, not a feature |
| Visa + Featurespace | consolidation | Visa closed the Featurespace acquisition in December 2024; it joins Visa Risk and Identity Solutions, so network-level scoring is becoming a Visa product | Scoring alone is commoditising; adaptation on the customer's own data is where a small vendor can stand out |
| Visa VAMP | market pressure | Merchant "Excessive" ratio 1.5% (150 basis points) from 1 April 2026 in the US, Canada, Europe and Asia Pacific, with at least 1,500 fraud-and-dispute counts a month; an enumeration (card-testing) ratio of 20% with a 300,000-authorisation floor; fines per count (sources quote $5 to $10; several say $8); fines in force since October 2025 | The number Priya is afraid of. Drawing it on a chart of her own ratio is the cheapest way to speak her language |

Sources: [Visa press release on Featurespace](https://corporate.visa.com/en/sites/visa-perspectives/newsroom/visa-completes-acquisition-featurespace.html),
[Forter on VAMP](https://www.forter.com/blog/visas-updated-vamp-program/), [Zolution on VAMP](https://zolution.io/learn/visa-acquirer-monitoring-program),
[Dispute Ops Desk on VAMP 2026](https://disputeopsdesk.pro/guides/visa-vamp-2026), [Stripe Radar features](https://stripe.com/au/blog/new-radar-features),
[Stripe Radar rules](https://stripe.com/en-dk/docs/radar/rules/reference), [chargeback.io on Kount alternatives](https://www.chargeback.io/blog/kount-alternatives),
[Sardine product updates](https://www.sardine.ai/blog/product-updates-september-2026), [Riskified chargeback guarantee](https://www.riskified.com/?p=325),
[Signifyd on BigCommerce](https://bigcommerce.com/apps/signifyd). Vendor pages are marketing; the VAMP numbers vary across sources, so check Visa's fact sheet before putting them in customer-facing copy.

## Capability gaps

| Capability | Table stakes? | Who offers it | Concours today | Recommendation |
|---|---|---|---|---|
| Case management and review workflow (assignee, status, notes, ageing, bulk actions) | Yes | Stripe, Adyen, Sift, Kount, Sardine, SEON | Verdict buttons only | Build the basics next quarter (days); this week: status column in the CSV so it fits their existing tracker |
| Explanations per case | Yes | Sift signals, Sardine evidence bundles, Radar risk insights | Three plain-English reasons per case, from feature contributions | Keep; vary the phrasing and add the numbers behind them ("$412, 6x this customer's usual") |
| Rules alongside models | Yes | all scoring platforms; Sardine with backtests | None (two velocity rules live inside one solver) | Later: a small rule list (amount over X, new terminal, N payments in an hour) with a backtest on the holdout that shows money per day; this is also how analysts' intuition enters the system |
| Dispute and chargeback tracking | Yes | Stripe, Adyen, Sift, Riskified, Signifyd | Labels only (fraud / not fraud, with a confirmation date) | This week: a monthly ratio from the labels; later: import of dispute files with reason codes and outcomes |
| Dispute-ratio monitoring against Visa thresholds | Becoming table stakes | Stripe benchmarks, chargeback vendors | None | This week: monthly fraud-and-dispute ratio with the 1.5% line and the count floor |
| Alerts and digests (daily queue email, slipping alert) | Yes | all | None (health is a screen) | Later: daily queue CSV by email, slipping alert; a few hours each once email exists |
| Integrations (CSV, webhooks, API) | Yes | all | CSV in and out, a CLI, an authenticated API | This week: make the CSV Excel-safe and complete; later: a webhook when the queue is ready and a scored-rows endpoint |
| Benchmarking against the customer's current tool | Differentiator if done | Stripe benchmarks against peers, not against your own tool | None | This week: accept the current score as an optional column and show "versus your current tool" everywhere the model's number appears |
| Model version history | Yes | most | Versions with scores and gates | This week: "what changed" in plain English per version |
| Continuous improvement on the customer's own data | Differentiator | nobody at this price point | Local rounds, Apex package | Emphasise; label local versus live honestly |
| Promotion gates a non-engineer can read | Differentiator | nobody | Five gates with plain names | Emphasise; explain each gate in one sentence on hover (exists) and in the "what changed" note |
| Drift response | Differentiator | enterprise vendors retrain on their schedule | Health plus PSI, round on drift | Emphasise; keep the jump button for demos only |
| Real-time decisions at checkout | Table stakes for e-commerce fraud vendors | all | Out of scope (batch queue) | Say so plainly on the trust page; position for post-authorisation review teams |

## Differentiators to emphasise

1. The model keeps improving on your data, not on a vendor's average customer, and every improvement is
   measured in money per day inside your team's capacity.
2. Promotion is earned: five gates, in words anyone can read, on days the model never saw.
3. Honest measurement: late labels, an embargo, hidden test days. Competitors report a score; Concours
   reports what would have happened.
4. Drift is detected and answered with a new round, not a support ticket.

Table stakes to gesture at this week: a status column and Excel-safe export (fits the analysts' existing
tracker), the Visa ratio card, "what changed" notes, a trust page. Say "coming" for case workflow, rules and
alerts rather than hiding them.

## Ideas evaluated

| Idea | Verdict | Why | Effort |
|---|---|---|---|
| Accept the existing fraud score as an input and show "versus your current tool" | Yes, this week | The persona's first question is "better than what I have?"; an optional `current_score` column ranked the same way on the holdout answers it in her units ($/day) with no new ML | a few hours |
| Dispute-ratio tracker with the Visa threshold drawn on it | Yes, this week | Monthly `frauds / payments` from the labels, with the 1.5% line and the 1,500-count floor; label it "from your labels" since true disputes need a dispute file | a few hours |
| "What changed" notes per version | Yes, this week | The gate results and the improvement line already hold the facts; three sentences per version | a few hours |
| Trust page | Yes, this week | Every security question from a buyer, answered once: what leaves the machine (nothing, except the package you download), who sees what (solvers: hashed IDs and training rows; Macrocosmos: the referee image), what Apex is | a few hours |
| Exploration slots (5% random cases) | Yes, this week | Ten random cases a day make analyst verdicts informative about what the model misses; mark them "random check" so analysts know why | under 1 hour |
| Queue export that fits analyst tools | Yes, this week | Add status, reviewer and note columns, keep transaction ID as the key, escape formulas | under 1 hour |
| "Live versus local" indicators everywhere results appear | Yes, this week | Required for honesty and by the demo plan | a few hours |

## Top 10 improvements, ranked by impact over effort

| # | Improvement | Impact | Effort | Tag |
|---|---|---|---|---|
| 1 | Upload survives a real CSV: currency symbols and thousands separators, mixed date formats, blank amounts dropped with a count, more column-name patterns, the date range and window row counts shown before protection, and a refusal with a sentence when a window is empty | Unblocks every real customer; prevents the queue crash | a few hours | build this week |
| 2 | "Live versus local" status and "Apex-compatible local run" labels on Improve and Launch | Honesty; demo | a few hours | build this week |
| 3 | Excel-safe exports with status, reviewer and note columns | Security; fits existing tools | under 1 hour | build this week |
| 4 | "Versus your current tool": optional current-score column, compared on the holdout | The first question every buyer asks | a few hours | build this week |
| 5 | Dispute-ratio card against the Visa 1.5% line | Speaks the persona's fear in her numbers | a few hours | build this week |
| 6 | "What changed" per version | Trust in promotions | a few hours | build this week |
| 7 | Trust page | Shortens security review | a few hours | build this week |
| 8 | Exploration slots (5% random) in the queue | Better labels, blind-spot discovery | under 1 hour | build this week |
| 9 | Case management basics: assignee, status, notes, filters, ageing | Table stakes for daily use | days | later |
| 10 | Alerts and digests (daily queue email, slipping alert) and a rules list with holdout backtests | Table stakes | days | later |

Also later: progress and time estimates for Docker runs (a few hours; worth doing right after the demo),
hide the jump button on real projects (under 1 hour; included with item 2 as a demo flag), a dispute-file import
with reason codes (days), webhooks and a scored-rows API (days).

## Status after Phase 2 (2026-10-29)

Built this week, in the commit `Customer journey quick wins` (and `Plan B ...` for the indicator):

- Walk 2 again, same `messy.csv`, no cleaning: upload 1.4 s, columns suggested for all five required fields,
  confirmation accepted in 9.9 s with the notes "3 date formats found in this column; all were read", "Dates
  with slashes were read as day/month/year" and "4,206 payments without an amount or a time will be left out";
  the three questions and protection went through (2.7 s). The two planted leak columns were caught as before.
- Protection now refuses a public-check or private-test window with under 200 payments, with the file's date
  range in the sentence, instead of building a model on nothing.
- The queue holds 10 random checks a day (5% of 200), marked "Random check" with the reason "not a model pick".
- "Versus your current tool" appears on the Overview when a `current_score` column is mapped (kept as a feature).
- A fraud-and-dispute ratio card by month with Visa's 1.5% line on the Overview (the sample's September, with
  the injected card-testing pattern, sits at 2.8%).
- "What changed" lines per version, a Trust page, Excel-safe exports with the random checks marked, the live
  versus local indicator on Improve and Launch, and the demo jump control hidden on real projects.

Not done this week (tagged later above): case management basics, alerts and digests, rules with backtests,
a dispute-file import, webhooks and a scored-rows API, progress estimates for cold Docker runs, the chat
questions as a form.
