# Model card — demo-001

## Model

XGBoost binary classifier (`binary:logistic`), 300 trees with early stopping on validation PR-AUC, depth 4, learning rate 0.08, `scale_pos_weight` set from the training prevalence.

Inference uses `best_iteration` (43 of 300). Saving a booster and predicting with all trees is the classic early-stopping bug; the scorer passes an explicit `iteration_range`.

## Intended use

Demonstration of a fraud-scoring pipeline on synthetic data. It exists to show feature computation, imbalance-aware evaluation, explanation generation, and the review workflow.

**Not intended for:** real account decisions, production risk scoring, or any use where a person is affected.

## Training data

- `data/demo/transactions.csv`, generated deterministically by `src/nexvia_fraud/data/generate_demo.py` (seed 7, 5,000 rows, 30 days).
- ~600 cards. Fraud is injected as rings of 2–5 cards sharing a device and email domain.
- Deliberate difficulty: 35% of ring transactions revert to the card's own entities (evasion), 6% of legitimate transactions use a shared device/domain, and 1% of labels are flipped.
- No real customer data. No Kaggle data is redistributed.

Split: time-ordered. The first 70% trains, the next 10% selects the early-stopping iteration, and the final 20% is the untouched test window (`validation_start` and `test_start` in `artifacts/demo/metrics.json`).

## Features

13 point-in-time features, computed strictly from transactions before the scored event:

| Group | Features |
|---|---|
| Velocity | `velocity_1h`, `velocity_24h`, `unique_devices_24h` |
| Amount profile | `amount_mean`, `amount_std`, `amount_zscore` |
| Entity change | `device_change`, `email_change`, `addr_change` |
| Recency | `seconds_since_last_txn` |
| Network | `device_share_count`, `email_share_count`, `addr_share_count` (distinct cards seen on the entity before `t`) |

## Metrics (run `demo-001`)

Metrics are computed on the untouched final 20% window. Early stopping selected iteration 17 using a separate validation slice.

| Metric | Value |
|---|---|
| PR-AUC (average precision) | 0.740 |
| ROC-AUC | 0.877 |
| Precision @ 1% FPR | 0.836 |
| Recall @ 1% FPR | 0.719 |
| Precision @ 100 | 0.480 |
| Test prevalence | 6.4% |
| Train / validation / test rows | 3,500 / 500 / 1,000 |
| Test fraud rows | 64 |

Why PR-AUC: with a ~6% positive rate, ROC-AUC hides precision collapse. PR-AUC's baseline is the prevalence, so 0.740 is meaningfully above 0.064.

## Unknown-card defaults

When the card has no history:

| Feature | Default |
|---|---|
| `velocity_1h`, `velocity_24h`, `unique_devices_24h` | 0 |
| `amount_mean`, `amount_std`, `amount_zscore` | 0 |
| `device_change`, `email_change`, `addr_change` | 0 |
| `seconds_since_last_txn` | -1 |
| `device_share_count`, `email_share_count`, `addr_share_count` | counts from other cards on the supplied entity (may be > 0) |

The entity share counts are non-zero even for a new card, because the device/email/address may already be linked to other cards. That is intentional cold-start signal.

## Explanation

TreeSHAP contributions are stored per transaction and shown in the case detail. Positive contributions push toward fraud (log-odds). SHAP explains the model, not causality.

## Known limitations

- Synthetic data; the ring structure is simpler than real fraud.
- Label noise is injected uniformly and does not model delayed chargebacks.
- Single time split; no rolling-origin validation yet.
- No fairness analysis: device/email/address features can proxy for geography or income.
- Precision @ 100 is modest (0.49), so the top of the queue still contains false positives.

## Drift monitoring

`artifacts/demo/reference_features.parquet` stores the training distribution of all 13 features (3,500 rows). The drift job compares it to the most recent 500 scored transactions using Evidently's `DataDriftPreset`. Evidently chooses the per-column test from the window size: p-value tests (K-S, chi-square, Z-test) for small windows, and distance metrics (Jensen-Shannon, normalised Wasserstein) for larger ones. Each method's own threshold decides whether a column drifted. A drifted-column share at or above `DRIFT_SHARE_THRESHOLD` (default 0.50) creates one open retraining request. Fewer than 50 current rows reports `insufficient_data`.

Drift is covariate drift only. It does not observe concept drift (`P(y|x)` changing), and the synthetic labels have no delayed feedback, so a drift report is an early warning, not proof of performance loss.

## Ethical notice

Fraud systems make consequential decisions about people. A real deployment needs human adjudication, appeal paths, fairness testing, and regulatory review. None of that is present here.
