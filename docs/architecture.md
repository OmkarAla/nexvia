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
```

## Audit chain

Each row hashes `prev_hash || canonical_json(payload)`. Verification walks the chain from the genesis value and compares every link. Mutation of any row breaks its hash and every subsequent link. Truncation of the tail is **not** detectable without an externally anchored head — documented in `docs/limitations.md`.

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
