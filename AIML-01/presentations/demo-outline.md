# 10-minute demo outline

## 0:00–0:40 — Frame

- What it is: real-time fraud scoring with a review workflow.
- What it is not: not production, synthetic data, no real customers.
- What to look for: the seams (idempotency, point-in-time features, audit), not the model accuracy.

## 0:40–2:00 — Architecture

- Producer → Kafka → consumer → feature service → XGBoost → Postgres → dashboard.
- One scoring function shared by the consumer and the API.
- At-least-once delivery + idempotent writes.

## 2:00–4:30 — Live demo

1. Live feed: transactions arriving at 2/s.
2. Case queue: filter by score, open a high-score alert.
3. Case detail: amount, card, prior cases, SHAP bars.
4. Reject with a reason; show the status change and audit hash.
5. `/audit` returns `valid: true`.

## 4:30–6:00 — Model evidence

- Time-based split, prevalence 6.4%.
- PR-AUC 0.771 vs baseline 0.064; ROC-AUC 0.893.
- Precision/recall at 1% FPR; precision@100.
- Why PR-AUC, not accuracy or ROC-AUC alone.
- Best iteration 43/300 — why the scorer passes `iteration_range`.

## 6:00–7:00 — Correctness stories

- Duplicate Kafka delivery produces one alert (test).
- A card with no history scores with defaults (test).
- A feature at time `t` never sees `t` or later (test).
- Second decision on the same alert is rejected (409).

## 7:00–8:00 — Limits

- Synthetic data, no delayed labels, one time split.
- No Feast/GNN/drift/K8s yet — next phase.
- No auth; do not expose publicly.
- Audit truncation is undetectable.

## 8:00–9:00 — What I would do next

- Feast parity test, then the GNN and the OOF stacker.
- Evidently drift + a human-gated retraining request.
- Rolling-origin validation and calibration.

## 9:00–10:00 — Questions

Have `docs/api.md`, `docs/model-card.md`, and `docs/limitations.md` open for reference.
