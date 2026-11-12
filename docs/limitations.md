# Limitations and non-goals

This is a vertical slice. The following are deliberate gaps, not oversights.

## Data

- **Synthetic only.** The demo generator injects rings, evasion, shared-entity false positives, and label noise, but it is still a simulation. Metrics do not transfer to IEEE-CIS or real traffic.
- **No delayed labels.** Real chargebacks arrive weeks later; this demo has labels at event time.
- **One time split.** The held-out window is the final 20% by time. There is no rolling-origin validation or backtest across quarters.

## Model

- **XGBoost only.** The GNN (GraphSAGE on a heterogeneous card/device/email/address graph) and the logistic stacker are the next phase. `mode` is always `xgb_only`.
- **Hand-built features.** Feast (offline Parquet, online Redis, point-in-time joins) is not wired yet. `FeatureService` preserves the interface but recomputes from the demo frame in memory.
- **No drift monitoring.** Evidently, drift reports, and retraining requests are not implemented in this slice.
- **No calibration.** Scores are used as ranking and threshold inputs. A reliability diagram is not yet produced.

## Streaming

- **Single broker, at-least-once.** No replication, no transactionally consistent sink. Idempotency comes from the database keys, not from Kafka exactly-once.
- **One partition count, no rebalancing tests.** The consumer group has one member in the demo.
- **Poison-pill handling commits and logs.** That avoids a stuck partition but drops the message; no dead-letter topic yet.

## API and product

- **No authentication.** The design calls for a seeded demo JWT with three roles; the slice ships without auth and must not be exposed publicly as-is.
- **No rate limiting** and no request size limits beyond Pydantic validation.
- **Audit chain truncation is undetectable.** A deleted tail leaves a valid chain. A real system anchors the head externally or signs checkpoints.
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

Per the design doc §12: Feast, GNN + blender, Evidently drift, retraining requests, K8s manifests, then the imaging repo.
