# Churn template data source

`dataset.csv` is the UCI Machine Learning Repository dataset 563, "Iranian Churn Dataset",
https://archive.ics.uci.edu/dataset/563/iranian+churn+dataset, downloaded by
`scripts/fetch_data.py`. 3,150 rows, 14 columns. Features are aggregates of the first 9 months;
`Churn` is the customer state at month 12.

License: CC BY 4.0. Credit: UCI Machine Learning Repository.

Note: three column names carry a double space in the original file (`Call  Failure`,
`Subscription  Length`, `Charge  Amount`). They are kept verbatim.
