# Limitations and non-goals

This is a vertical slice. The following are deliberate gaps, not oversights.

## Data

- **Synthetic only.** The demo generator injects rings, evasion, shared-entity false positives, and label noise, but it is still a simulation. Metrics do not transfer to IEEE-CIS or real traffic.
- **No delayed labels.** Real chargebacks arrive weeks later; this demo has labels at event time.
- **One chronological holdout.** Train/validation/test are sequential slices of one window. There is no rolling-origin validation or backtest across quarters.
- **Real-data model is a 30k sample.** IEEE-CIS training uses 30,000 of 590,540 rows for runtime reasons; the EDA covers the raw set. The 386-feature real model is separate from the 13-feature demo model.

## Model

- **Graph is a snapshot.** Serving embeddings come from a graph containing all data up to the nightly job. Evaluation avoids future edges by using a pre-test graph. A streaming graph update is not implemented.
- **GNN labels are card-level.** A card is fraudulent if any transaction in the training window is fraudulent. That captures card reuse, but it is not the same target as transaction-level fraud.
- **Single-fold blender.** Blend weights are fit on one validation window, not on full out-of-fold folds across time.
- **Feast keys transactions, not cards, for serving.** The online lookup is exact for replayed events and avoids future leakage, but it assumes the feature row was materialized before scoring. In production a streaming writer would maintain the online store; unknown transactions fall back to the in-process provider.
- **Drift is covariate only.** Evidently compares feature distributions to the training reference. Concept drift (`P(y|x)` changing) and delayed-label performance are not observed. A drift breach raises a request; it is not proof of degradation.
- **No calibration.** Scores are used as ranking and threshold inputs. A reliability diagram is not yet produced.

## Streaming

- **Single broker, at-least-once.** No replication, no transactionally consistent sink. Idempotency comes from the database keys, not from Kafka exactly-once.
- **One partition count, no rebalancing tests.** The consumer group has one member in the demo.
- **Poison-pill handling commits and logs.** That avoids a stuck partition but drops the message; no dead-letter topic yet.

## API and product

- **No authentication.** The design calls for a seeded demo JWT with three roles; the slice ships without auth and must not be exposed publicly as-is.
- **No rate limiting** and no request size limits beyond Pydantic validation.
- **Audit chain truncation is detectable only through the stored head row.** The chain verifier checks the head hash, so deleting a tail row breaks verification unless an attacker also edits `audit_head` in the same database. External anchoring is not implemented.
- **Dashboard has two views.** There is no separate model/drift page, audit page, or linked-entity graph yet; the audit is available via `/audit`.

## Operations

- **CPU only.** Latency was measured on one dev machine with SQLite at ~51 req/s sequential. It is not a capacity claim.
- **Hosted deployment deferred.** Render/Vercel/Upstash/R2 configuration is not part of this slice.
- **Kubernetes deferred.** Fraud requires manifests in the final submission; none exist yet.
- **Free-tier behavior untested.** Cold starts, ephemeral disks, and managed Kafka quotas are unmeasured.

## Security and privacy

- No PII is present because the data is synthetic. A real deployment would need field-level redaction, retention rules, and access audit.
- Secrets are environment variables; no secret scanning is configured.
- Dependency and container scanning are not configured.

## Next phase

Per the design doc Â§12: Feast, GNN + blender, Evidently drift, retraining requests, K8s manifests, then the imaging repo.
