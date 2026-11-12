# API

Base URL: `http://localhost:8000`. Interactive docs at `/docs`.

All timestamps are ISO-8601 UTC with a `Z` suffix; inputs with another offset are converted to UTC.

## GET /health

```json
{ "status": "ok", "model_version": "demo-001" }
```

## POST /score

Scores one transaction and persists it. Raises an alert when the score is at or above `ALERT_THRESHOLD`.

```json
{
  "transaction_id": "txn-000123",
  "card_id": "card-0042",
  "event_time": "2026-01-05T10:15:00Z",
  "amount": 149.99,
  "device_id": "card-0042-primary",
  "email_domain": "gmail.com",
  "addr_id": "addr-042"
}
```

`device_id`, `email_domain`, and `addr_id` are optional and default to `unknown-*`.

A naive `event_time` (no offset) is rejected with `422`; aware timestamps are normalized to UTC and returned with a `Z` suffix.

Response:

```json
{
  "transaction_id": "txn-000123",
  "score": 0.83,
  "mode": "xgb_only",
  "model_version": "demo-001",
  "top_features": [
    { "feature": "device_share_count", "value": 4.0, "contribution": 0.61 }
  ]
}
```

`top_features` is TreeSHAP in log-odds space, sorted by absolute contribution, capped at 10.

Replaying the same `transaction_id` updates the stored score and does not create a second alert.

## POST /score/batch

```json
{ "transactions": [ { "...": "same shape as /score" } ] }
```

Returns `{ "scores": [ ... ] }`. An empty list returns an empty list.

## GET /transactions?limit=100

Returns the most recent scored transactions, newest first. `limit` is 1–500.

## GET /alerts?status=open&min_score=0.5&limit=50

Returns alerts sorted by score descending. `status` is `open`, `approved`, `rejected`, or omitted for all.

```json
{
  "alerts": [
    {
      "id": "9f2c...",
      "transaction_id": "txn-000123",
      "score": 0.83,
      "status": "open",
      "reason": null,
      "assignee": null,
      "created_at": "2026-01-05T10:15:01Z"
    }
  ]
}
```

## GET /alerts/{id}

```json
{
  "alert": { "...": "alert object" },
  "transaction": { "...": "transaction facts and features" },
  "top_features": [ { "feature": "...", "value": 0, "contribution": 0 } ],
  "prior_cases": 0
}
```

## POST /alerts/{id}/decision

```json
{ "decision": "reject", "reason": "matches a known ring", "analyst": "ana" }
```

- `200` — decision recorded; returns `{ "alert", "decision_id", "audit_hash" }`.
- `404` — alert does not exist.
- `409` — alert was already decided (or the reason/analyst is empty).

## GET /audit

```json
{
  "entries": [
    {
      "id": 1,
      "prev_hash": "000...000",
      "hash": "b4c1...",
      "payload": { "event": "decision", "alert_id": "...", "decision": "reject" },
      "created_at": "2026-01-05T10:16:00Z"
    }
  ],
  "valid": true
}
```

## GET /metrics

Prometheus text format:

```
fraud_score_requests_total 300
fraud_score_latency_seconds{quantile="0.5"} 0.018812
fraud_score_latency_seconds{quantile="0.95"} 0.023204
fraud_score_latency_seconds{quantile="0.99"} 0.040771
```

Latency is measured in-process over the last 2,000 requests, not a histogram.

## GET /drift/latest

`200` with `{"report": null}` before the first job run. Otherwise:

```json
{
  "report": {
    "id": "1f2c...",
    "created_at": "2026-01-06T09:00:00Z",
    "drift_share": 0.31,
    "dataset_drift": true,
    "n_reference": 3500,
    "n_current": 120,
    "method": "evidently:DataDriftPreset",
    "columns": [
      { "column": "amount_zscore", "score": 0.42, "method": "Wasserstein distance (normed)", "drifted": true }
    ]
  }
}
```

## GET /retraining-requests

```json
{
  "requests": [
    {
      "id": "q9...",
      "drift_report_id": "1f2c...",
      "reason": "drift share 0.60 >= 0.50",
      "status": "open",
      "created_at": "2026-01-06T09:00:01Z",
      "resolved_at": null,
      "resolved_by": null
    }
  ]
}
```

At most one request is `open` at a time.

## POST /retraining-requests/{id}/resolve

```json
{ "status": "approved", "resolved_by": "ana" }
```

- `200` — `{ "request": { ..., "status": "approved" } }`
- `404` — request does not exist
- `409` — request was already resolved

Resolving a request does not retrain or promote anything; it records a human decision.
