# IEEE-CIS Fraud Detection — EDA

Generated from `train_transaction.csv` + `train_identity.csv`.

## Class imbalance

- Raw rows: **590,540**
- Fraud rate (raw): **3.4990%**
- Rows used for the demo training set: 150,000
- Fraud rate (used): 3.4660%

This is the heavy imbalance the brief calls out. Accuracy is meaningless; the project evaluates with PR-AUC and precision/recall at a fixed FPR.

## Time range and cards

- 2017-12-01 00:00:01+00:00 → 2018-05-31 23:57:27+00:00
- Distinct cards: 9,016

## Amounts

- Mean: 134.55
- Median: 68.50
- p99: 1104.00

## Missingness

- Identity row coverage: 24.42% of transactions
- Missing email domain: 15.99%
- Missing address: 11.13%

## Top email domains

- `gmail.com`: 59,095
- `yahoo.com`: 26,490
- `unknown.example`: 21,108
- `hotmail.com`: 11,767
- `anonymous.com`: 9,821
- `aol.com`: 7,207
- `comcast.net`: 2,012
- `icloud.com`: 1,653
- `outlook.com`: 1,311
- `msn.com`: 1,085

## Fraud rate by day (first five)

- 2017-12-01: 2.961% of 1,317 transactions
- 2017-12-02: 3.154% of 983 transactions
- 2017-12-03: 2.750% of 800 transactions
- 2017-12-04: 3.800% of 1,079 transactions
- 2017-12-05: 3.842% of 1,015 transactions

## Notes

- The loader maps card1/DeviceInfo/email/addr1 into the project schema; the mapping is documented in `src/nexvia_fraud/data/load_ieee.py`.
- The demo artifacts in `artifacts/demo/` remain synthetic; real-data artifacts are written to `artifacts/ieee/`.
