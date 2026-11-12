# Architecture

## Context

```mermaid
flowchart LR
    subgraph Producer
        CSV[demo CSV] --> R[replay.py]
    end
    R -->|JSON keyed by card_id| K[(Kafka<br/>transactions.raw)]
    K --> C[consumer worker]
    C --> FS[FeatureService]
    FS --> SC[XGBoost booster + TreeSHAP]
    SC --> PG[(Postgres)]
    PG --> API[FastAPI]
    API --> REACT[React dashboard]
    SC -->|score >= 0.5| PG
```

## Scoring path

```mermaid
sequenceDiagram
    participant P as producer
    participant K as Kafka
    participant C as consumer
    participant F as FeatureService
    participant M as Scorer
    participant D as Postgres
    participant U as Dashboard

    P->>K: publish transaction (key = card_id)
    K->>C: deliver (at-least-once)
    C->>F: get_features(card, t, amount, entities)
    F-->>C: 13 point-in-time features
    C->>M: score(features)
    M-->>C: probability + top-10 SHAP contributions
    C->>D: upsert transaction (idempotent)
    alt score >= threshold
        C->>D: create alert if absent
    end
    C->>K: commit offset
    U->>D: poll alerts + transactions
```

## Why the API and consumer share code

`score_transaction()` is the only place that assembles features, runs the model, persists the transaction, and raises an alert. The HTTP endpoint and the Kafka consumer both call it. This prevents the most common streaming bug: two scoring paths that drift apart.

## Idempotency

- Kafka delivers at least once.
- `transactions.id` is the transaction ID, so `upsert_transaction()` collapses replays.
- `alerts.transaction_id` is unique, so `create_alert_if_absent()` cannot duplicate a case.
- The consumer commits the offset only after the write succeeds.

## Data model

```mermaid
erDiagram
    TRANSACTIONS ||--o| ALERTS : "raised from"
    ALERTS ||--o| DECISIONS : "resolved by"
    AUDIT_LOG {
        int id PK
        string prev_hash
        json payload
        string hash
    }
    TRANSACTIONS {
        string id PK
        string card_id
        datetime event_time
        float amount
        json features
        json explanation
        float score
        string model_version
    }
    ALERTS {
        string id PK
        string transaction_id UK
        float score
        string status
        string reason
        string assignee
    }
    DECISIONS {
        string id PK
        string alert_id FK
        string decision
        string reason
        string analyst
    }
    DRIFT_REPORTS {
        int seq PK
        string id UK
        float drift_share
        bool dataset_drift
        json summary
    }
    RETRAINING_REQUESTS {
        int seq PK
        string id UK
        string drift_report_id FK
        string status
        string resolved_by
    }
    DRIFT_REPORTS ||--o{ RETRAINING_REQUESTS : "raises"
```

## Graph model and blend

```mermaid
flowchart LR
    T[training transactions] --> G[HeteroData<br/>card · device · email · addr]
    G --> S[GraphSAGE<br/>2 × SAGEConv]
    S --> P[gnn_card_scores.parquet]
    X[XGBoost probability] --> B[logistic blend<br/>log-odds]
    P --> B
    B --> O[final score<br/>mode = blended]
    X --> F[fallback<br/>mode = xgb_only]
```

- GraphSAGE is trained on cards from the training window with a seeded 70/15/15 card split, so test cards are unseen.
- Evaluation uses embeddings from a graph built only from rows before the test window. Serving uses a nightly full-graph precompute; that is a freshness/leakage trade-off documented in the model card.
- The blender is a two-coefficient logistic regression fit on the validation window. A card with no GNN score falls back to XGBoost-only, and the response says which path ran.

## Drift flow

```mermaid
sequenceDiagram
    participant T as Training
    participant R as reference_features.parquet
    participant J as drift-monitor
    participant E as Evidently
    participant D as Postgres
    participant U as Dashboard

    T->>R: write training distribution
    J->>R: read reference
    J->>D: read recent scored features
    J->>E: DataDriftPreset(reference, current)
    E-->>J: drift share + per-column distances
    J->>D: insert drift_reports
    alt share >= threshold
        J->>D: create one open retraining_request
    end
    U->>D: GET /drift/latest, /retraining-requests
    U->>D: resolve request (approved/rejected)
```

The job is deliberately conservative: insufficient current data returns `insufficient_data`, a missing reference returns `reference_missing`, and repeated runs during one episode do not create a second open request. A request is a prompt for a human, never an automatic retrain.

## Audit chain

Each row hashes `prev_hash || canonical_json(payload)`, and a singleton head row stores the latest hash under a row lock. Verification walks the chain from the genesis value and then compares the final link to the head. Mutation of a payload, or deletion of the tail, breaks verification. An attacker who can write both `audit_log` and `audit_head` can still rewrite history — external anchoring is not implemented (see `docs/limitations.md`).

## Deployment topology (hosted, later phase)

```mermaid
flowchart LR
    V[Vercel dashboard] --> RAPI[Render FastAPI]
    RAPI --> RP[(Render Postgres)]
    RCONS[Render consumer] --> UK[(Upstash Kafka)]
    RCONS --> RP
    RAPI --> UR[(Upstash Redis)]
```

Compose remains the full-fidelity demo. Hosted deployment is deferred until the depth phase.
