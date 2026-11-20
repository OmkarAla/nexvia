# Reflection - AIML-01 (Nexvia Fraud)

## Name and role

- Name: Omkar Ala (sole intern)
- Role: AI / Machine Learning
- Owned area(s): data generation and the IEEE-CIS adapter, feature engineering (Feast), XGBoost and GraphSAGE training, the blender, drift monitoring, the scoring API, the review dashboard, tests, and the deployment/docs.

## What I built

- `src/nexvia_fraud/data/generate_demo.py` and `data/load_ieee.py` - deterministic synthetic data and the IEEE-CIS schema adapter.
- `features/service.py` and `feature_repo/` - 13 point-in-time features, Feast historical retrieval, transaction-keyed online serving, parity tests.
- `models/train.py`, `models/train_ieee.py`, `models/gnn.py`, `models/blend.py` - XGBoost, heterogeneous GraphSAGE, and the logistic blend.
- `streaming/` - Kafka producer and at-least-once consumer with idempotent writes.
- `drift/` - Evidently reports and the automatic retraining request.
- `api/`, `db/`, `audit/` - scoring, cases, decisions, and the hash-chained audit log.
- `dashboard/` - live feed, case queue, SHAP case detail, model health.

The decision I would defend in an interview: **using a transaction-keyed Feast view for serving**. It looks unusual because feature stores are usually card-scoped, but it is what makes replay exact without leaking future card state.

## What broke

- **Pandas 3 datetime units.** Feature timestamps were silently stored in microseconds while query timestamps were nanoseconds, so every velocity window was wrong. The test caught it; the fix was an explicit `datetime64[ns, UTC]` cast.
- **Consumer committed on failure.** A database error still committed the Kafka offset, dropping transactions. I changed it to commit only after a successful write and to let failures restart the consumer.
- **Audit chain forked.** Two concurrent appends could both read the same head hash. The fix was a locked head row plus truncation detection.
- **Concurrent duplicate writes.** Check-then-insert produced 500s under duplicate delivery. I replaced it with `ON CONFLICT` upserts inside one transaction.
- **Graph leakage.** Full-graph inference inflated the GNN and blend scores. I rebuilt the evaluation on a pre-test graph.
- **Evidently method switch.** It uses p-value tests for small windows and distance metrics for large ones; my parser assumed p-values. I now infer the direction from the method name.

## What I learned

- I can explain **why at-least-once delivery plus an idempotent sink is the honest design** for this stack, and why "exactly-once" claims with a Postgres sink are wrong.
- I can explain **point-in-time correctness** and why a random split inflates fraud metrics.
- I am still less confident under pressure on **streaming feature-store updates**: the transaction-keyed view is exact for replay, but a streaming writer for card state is the next real engineering step.

## What I would do differently

- I would **vectorize the feature computation** before training on IEEE-CIS. The per-row loop forced a 30k sample; a vectorized pipeline would train on the full 590k rows.
- I would start Docker and the Kubernetes cluster earlier, instead of validating manifests statically for most of the project.

## Evidence

- Commit range: `09657ea` through the final submission commit.
- Run IDs: `demo-002-feast`, `demo-gnn-001`, `ieee-raw-001`, `ieee-gnn-001`.
- Metrics: demo PR-AUC 0.740 / blended 0.839; IEEE-CIS sample PR-AUC 0.455; GNN card PR-AUC 0.531.
- Demo timestamp: the fraud recording linked from the README.
