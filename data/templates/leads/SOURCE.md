# Leads template data source

`dataset.csv` is built by `scripts/fetch_data.py` from `bank-full.csv` inside the UCI Machine Learning
Repository dataset 222, "Bank Marketing", https://archive.ics.uci.edu/dataset/222/bank+marketing
(Moro, Rita and Cortez, 2014). 45,211 phone contacts from a Portuguese bank's term-deposit campaigns,
May 2008 to November 2010. Target `y` is whether the contact ended in a subscription (11.7% yes).

License: CC BY 4.0. Credit: UCI Machine Learning Repository; S. Moro, P. Rita and P. Cortez, "A
Data-Driven Approach to Predict the Success of Bank Telemarketing", Decision Support Systems, 2014.

Changes from the source file: the `;` separator is replaced by `,`. Columns are as published.

No time column. The file has `month` and `day` but no year. Rows are ordered by date and the campaign's
last months are a different regime (about a third of contacts convert, against 6% at the start), so a
split by time trains on one campaign and tests on another and no solver beats the baseline. The
template splits stratified, like churn, and says so on the protect screen.

Planted leak the protect step must catch: `duration`, the length of the call in seconds. It is only
known after the call and long calls are the ones that convert (single-feature AUC 0.81). The dataset's
own notes say it should be discarded for a realistic model. It sits below the statistical leak
thresholds, so the template lists it under `known_leaks` in `defaults.json`.
