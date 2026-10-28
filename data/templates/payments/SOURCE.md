# Missed payments template data source

`dataset.csv` is built by `scripts/fetch_data.py` from UCI Machine Learning Repository dataset 350, "Default of
Credit Card Clients", https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients (Yeh and Lien,
2009). 30,000 credit card holders in Taiwan, April to September 2005. Target `default_next_month` is whether
the next payment was missed (22.1% yes).

License: CC BY 4.0. Credit: UCI Machine Learning Repository; I-C. Yeh and C-H. Lien, "The comparisons of data
mining techniques for the predictive accuracy of probability of default of credit card clients", Expert
Systems with Applications, 2009.

Changes from the source file: UCI's `data.csv` names the columns `X1`..`X23` and `Y`; the names from the
original spreadsheet's header row are restored (`LIMIT_BAL`, `SEX`, ..., `PAY_AMT6`) and `Y` is named
`default_next_month`. Values are as published.

Framing: the list is for early outreach (a call offering help, a payment plan), never for approving or
declining credit. `SEX`, `MARRIAGE` and `AGE` are set aside by Protect and used only for the fairness report.
`ID` is dropped as an identifier.
