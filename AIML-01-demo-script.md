# AIML-01 — Fraud demo recording script

**URL:** http://localhost:5173
**API:** http://localhost:8000 (for the `/audit` tab)
**Target length:** 6–7 minutes
**Format:** 1080p, 30 fps, narrated. Do not show terminals, `.env`, or tokens.

The stack is already running: 32 open alerts, one drift report at 46.2%, one retraining request.

---

## Pre-flight (before you hit record)

1. Open two browser tabs:
   - `http://localhost:5173`
   - `http://localhost:8000/audit`
2. Refresh the dashboard. Confirm the queue says **32 shown**.
3. Hide bookmarks (`Ctrl+Shift+B`), zoom 100%, close other apps.
4. Test 10 seconds of audio, then start the real take.

---

## 0:00–0:35 — Opening

**On screen:** dashboard header, banner, case queue.

**Say:**

> "This is AIML-01, Nexvia Fraud: a real-time transaction fraud platform. A producer replays a transaction stream into Kafka, a consumer scores each transaction with XGBoost and a GraphSAGE graph model, and alerts land in Postgres. Analysts review them here. Everything is synthetic demo data — this is not a production fraud engine."

> "The stack is Kafka, FastAPI, PostgreSQL, React, Feast for feature definitions, MLflow for experiment tracking, Evidently for drift, and Kustomize manifests for Kubernetes."

---

## 0:35–1:15 — Case queue

**Do:** stay on **Case queue**. Point at the list.

**Say:**

> "The producer replays at two transactions per second. Anything scoring above 0.5 opens a case. Right now there are 32 open alerts, sorted by score."

> "The transaction ID is the idempotency key: Kafka delivers at least once, but a replay upserts the same row instead of creating a duplicate alert."

---

## 1:15–1:55 — Live feed

**Do:** click **Live feed**.

**Say:**

> "This is the live feed of scored transactions. The score column is right-aligned now. The small B marker means the final score came from the blended XGBoost plus graph model; without it, the card had no graph embedding and we fell back to XGBoost only."

> "Scores are probabilities, not calibrated risk yet — that's a documented limitation."

---

## 1:55–3:15 — Case detail and SHAP

**Do:** click **Case queue**, then the top alert (`txn-002994`, about 97.9%).

**Say:**

> "This is a very high-score case. The amount, card, prior cases, and the model path are shown at the top. Mode is **blended**, and the GNN score is about 98%, so both models agree."

> "Below is the explanation. These are TreeSHAP contributions in log-odds space. `addr change` adds about 1.24, `addr share count` adds about 0.71, and `device share count` adds about 0.23 — the card is suddenly using a shared address and device. Negative bars, like email change, push the score down."

> "SHAP explains the XGBoost component only. The graph model changes the final probability; it is not part of this attribution."

---

## 3:15–3:55 — Decision

**Do:** type the reason, then click **Reject**.

Reason to type:

> `matches a known fraud ring — shared address and device`

**Say:**

> "I'll reject this case. The reason is required. The status moves to rejected and an audit hash appears. Every decision is appended to a hash-chained audit log."

---

## 3:55–5:05 — Model health and retraining request

**Do:** click **Model health**.

**Say:**

> "This page is Evidently drift monitoring. About 46% of the features have shifted relative to the training reference — mainly amount and share-count features. The training run wrote the reference distribution, and this report compares it with the last 500 scored transactions."

> "A breach above the threshold creates exactly one open retraining request. It does not retrain automatically — a human approves or rejects it. I'll approve it here."

**Do:** click **Approve** on the request.

> "The request is recorded. Promotion is still a separate, reviewed step."

---

## 5:05–5:40 — Audit log

**Do:** switch to the `/audit` tab.

**Say:**

> "The audit endpoint returns the chain and a validity flag. `valid: true` means every row links to the previous hash, and the tail matches the stored head. The payload shows the reject decision, the comment, and the analyst."

---

## 5:40–6:20 — Close

**Say:**

> "Results: PR-AUC 0.740 for XGBoost, 0.805 for the graph model, and 0.839 blended. Latency is p50 about 19 ms and p99 about 26 ms on CPU at the demo rate."

> "Limitations are documented: synthetic data, a single Kafka broker, Feast serving is parity-tested but the API still uses the in-process feature path, and the audit chain is not externally anchored. The point of the project is the seams — idempotency, point-in-time features, drift, and audit — not a production claim."

---

## Click checklist

1. Case queue (default)
2. Live feed
3. Case queue
4. Top alert
5. Reason → Reject
6. Model health → Approve request
7. `/audit` tab
8. End

## If something goes wrong

- **Queue is empty:** refresh; if still empty, tell me — do not re-seed mid-recording.
- **Clicked the wrong alert:** pick another high-score one; the story is the same.
- **A page is stale:** `Ctrl+R`.
- **You flub a section:** stop, delete the take, and restart from the nearest section. The demo is stateless except for the decision — if you already rejected the top case, pick the next alert.
