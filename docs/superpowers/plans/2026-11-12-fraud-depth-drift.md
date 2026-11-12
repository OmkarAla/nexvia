# Fraud Depth — Drift Monitoring and Retraining Requests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the mandated drift loop: Evidently compares live feature distributions to the training reference, stores a drift report, and raises a human-gated retraining request when the drifted-column share crosses a threshold.

**Architecture:** Training writes a `reference_features.parquet` snapshot of the training distribution. A scheduled job reconstructs recent feature vectors from Postgres, runs Evidently's `DataDriftPreset`, stores a `DriftReport`, and creates at most one open `RetrainingRequest` per drift episode. The API exposes the latest report and a resolve action; the dashboard adds a Model health tab.

**Tech Stack:** Evidently 0.7.23, pandas 2.2, SQLAlchemy 2, FastAPI, APScheduler-free loop script (a simple `--loop --interval` CLI), React.

**Spec:** `docs/superpowers/specs/2026-11-11-two-ml-platforms-design.md` §5.2 (Evidently), §5.4 (retraining request), §12 item 3.

## Global Constraints

- Evidently is mandatory; do not hand-roll PSI as the reported monitor.
- Reference = training distribution only. Current = recent scored transactions.
- A drift breach creates a request; it never retrains or promotes automatically.
- No drift report without at least `MIN_CURRENT_ROWS` (50) current rows.
- Repeated runs must not spam requests: at most one `open` request at a time.
- Drift job must be runnable from Compose (`drift-monitor` service) and as a one-shot CLI.
- All new API timestamps serialize as ISO-8601 `Z` (reuse `nexvia_fraud.timeutil`).

## Review Focus

- **Insufficient data:** an empty or tiny current window must produce `insufficient_data`, not a false alarm.
- **Identical distributions:** no drift and no request.
- **Repeated runs:** ten runs during one drift episode create one open request.
- **Resolve twice:** second resolve returns 409, not a silent overwrite.
- **Missing reference:** the job and the endpoint report the problem clearly instead of crashing at import.

---

### Task 1: Training writes the reference snapshot

**Files:**
- Modify: `src/nexvia_fraud/models/train.py`
- Test: `tests/test_train.py`

**Interfaces:**
- Produces: `artifacts/demo/reference_features.parquet` with columns `FeatureService.feature_names()` and `n_train` rows.

- [ ] **Step 1: Write the failing test**

```python
def test_training_writes_reference_snapshot(tmp_path, demo_df):
    metrics = train_model(demo_df, str(tmp_path), run_id="ref")
    reference = pd.read_parquet(tmp_path / "reference_features.parquet")
    assert len(reference) == metrics["n_train"]
    assert list(reference.columns) == metrics["feature_names"]
```

- [ ] **Step 2: Run it; expect failure** (`FileNotFoundError`).
- [ ] **Step 3: Implement** — after `X_train` is built, write `pd.DataFrame(X_train, columns=features).to_parquet(out / "reference_features.parquet", index=False)`.
- [ ] **Step 4: Run tests** → pass.
- [ ] **Step 5: Regenerate the demo artifact** (`python -m nexvia_fraud.models.train ...`).
- [ ] **Step 6: Commit.**

---

### Task 2: Drift and retraining persistence

**Files:**
- Modify: `src/nexvia_fraud/db/models.py`, `src/nexvia_fraud/db/repo.py`
- Test: `tests/test_drift_repo.py`

**Interfaces:**
- `DriftReport(id str PK, created_at, drift_share float, dataset_drift bool, n_reference int, n_current int, summary dict)`.
- `RetrainingRequest(id str PK, drift_report_id FK, reason str, status str = "open", created_at, resolved_at nullable, resolved_by nullable)`.
- `save_drift_report(session, summary: dict) -> DriftReport`.
- `latest_drift_report(session) -> DriftReport | None`.
- `create_retraining_request_if_absent(session, drift_report_id: str, reason: str) -> RetrainingRequest | None` — returns None if an `open` request exists.
- `list_retraining_requests(session, limit: int = 50) -> list[RetrainingRequest]`.
- `resolve_retraining_request(session, request_id: str, status: str, resolved_by: str) -> RetrainingRequest` — status in `approved|rejected`; raises `ValueError` if missing or already resolved.

- [ ] **Step 1: Failing tests** — one report saved/loaded; second open request suppressed; resolve updates; second resolve raises.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Commit.**

---

### Task 3: Evidently drift computation

**Files:**
- Create: `src/nexvia_fraud/drift/__init__.py`, `src/nexvia_fraud/drift/monitor.py`
- Test: `tests/test_drift_monitor.py`

**Interfaces:**
- `compute_drift(reference: pd.DataFrame, current: pd.DataFrame, threshold: float = 0.3) -> dict` returning:
  ```python
  {"drift_share": float, "dataset_drift": bool, "n_reference": int,
   "n_current": int, "columns": [{"column": str, "p_value": float, "drifted": bool}],
   "method": "evidently:DataDriftPreset"}
  ```
- Uses `evidently.Report([DataDriftPreset()])` with `DataDefinition(numerical_columns=list(reference.columns))`.
- Parse `snapshot.dict()["metrics"]`: `DriftedColumnsCount` gives the share; `ValueDrift` entries give per-column p-values (drifted when p < config threshold).

- [ ] **Step 1: Failing tests**

```python
def test_identical_frames_do_not_drift(demo_df):
    ref = _features(demo_df, rows=500)
    result = compute_drift(ref, ref.copy())
    assert result["drift_share"] == 0.0
    assert not result["dataset_drift"]

def test_shifted_column_is_detected(demo_df):
    ref = _features(demo_df, rows=500)
    current = ref.copy()
    current["amount_zscore"] += 10.0
    result = compute_drift(ref, current)
    drifted = {c["column"] for c in result["columns"] if c["drifted"]}
    assert "amount_zscore" in drifted
    assert result["drift_share"] > 0.0
```

- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Commit.**

---

### Task 4: Drift job

**Files:**
- Create: `src/nexvia_fraud/drift/job.py`, `scripts/drift_job.py`
- Test: `tests/test_drift_job.py`

**Interfaces:**
- `run_drift_check(session_factory, reference_path: str, threshold: float, min_rows: int = 50) -> dict`:
  - reads `reference_features.parquet`;
  - reads up to 500 latest `Transaction.features` rows, builds a DataFrame with the reference columns;
  - returns `{"status": "insufficient_data", "n_current": n}` when `n < min_rows`;
  - otherwise computes drift, saves a `DriftReport`, and when `drift_share >= threshold` creates a request with reason `f"drift share {share:.2f} >= {threshold:.2f}"`.
  - returns the summary plus `report_id` and `request_id | None`.
- `scripts/drift_job.py`: `--once` (default) or `--loop --interval 60`.

- [ ] **Step 1: Failing tests**
  - seed 60 transactions copied from the reference → `status == "ok"`, no request;
  - seed 60 transactions with 5 columns shifted and threshold 0.1 → request created;
  - seed 5 transactions → `insufficient_data`, no report.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Commit.**

---

### Task 5: API endpoints

**Files:**
- Modify: `src/nexvia_fraud/api/main.py`, `src/nexvia_fraud/api/schemas.py`, `src/nexvia_fraud/api/app.py`, `src/nexvia_fraud/config.py`, `.env.example`
- Test: `tests/test_api.py`

**Interfaces:**
- `GET /drift/latest` → `{"report": {...} | null}`; 200 with `report: null` before the first run.
- `GET /retraining-requests` → `{"requests": [...]}`.
- `POST /retraining-requests/{id}/resolve` body `{"status": "approved"|"rejected", "resolved_by": str}` → `{"request": ...}`; 404 missing, 409 already resolved.
- Settings: `drift_share_threshold: float = 0.3`, `drift_min_rows: int = 50`, `drift_interval_seconds: int = 60`, `drift_reference_path: str = "artifacts/demo/reference_features.parquet"`.

- [ ] **Step 1: Failing tests** — empty drift endpoint; save a report in the DB and read it; resolve request; resolve twice → 409.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Commit.**

---

### Task 6: Compose job

**Files:**
- Modify: `docker-compose.yml`, `tests/test_compose_config.py`
- Test: compose config lists `drift-monitor`.

- [ ] **Step 1:** add the service (`command: python scripts/drift_job.py --loop --interval 60`, same env, depends on Postgres healthy + seed completed).
- [ ] **Step 2:** `docker compose config -q` and the test pass.
- [ ] **Step 3: Commit.**

---

### Task 7: Model health tab

**Files:**
- Create: `dashboard/src/components/ModelHealth.tsx`, `dashboard/src/components/ModelHealth.test.tsx`
- Modify: `dashboard/src/App.tsx`, `dashboard/src/api.ts`, `dashboard/src/types.ts`, `dashboard/src/styles.css`

**Interfaces:**
- `getDriftLatest()`, `getRetrainingRequests()`, `resolveRetrainingRequest(id, body)`.
- Tab "Model health": drift share bar (0–100%), drifted-column table, request list with Approve/Reject buttons.
- Pure helper `driftTone(share)` → `stable | watch | drifted` (<0.1, <0.3, else).

- [ ] **Step 1:** failing Vitest for `driftTone` and the rendered table.
- [ ] **Step 2–4:** implement; `npm test` and `npm run build` pass.
- [ ] **Step 5: Commit.**

---

### Task 8: Docs

**Files:** `README.md`, `docs/architecture.md`, `docs/api.md`, `docs/model-card.md`, `docs/limitations.md`

- [ ] Document the reference window, the Evidently preset, thresholds, the "request not retrain" gate, the insufficient-data rule, and the manual resolve flow.
- [ ] Add the drift job to the demo script.
- [ ] Commit.

## Self-Review Notes

- Spec coverage: Evidently (§5.2), retraining request (§5.4), dashboard model page (§5.5), build order item 3.
- No GNN/Feast/K8s in this plan; they remain the next depth items.
- Review Focus each has an owning test in Tasks 1–5.
