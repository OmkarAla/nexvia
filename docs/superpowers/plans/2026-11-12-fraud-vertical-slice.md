# Fraud Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one end-to-end fraud path — producer → Kafka → FastAPI scorer (XGBoost) → Postgres → React review dashboard — runnable from a clean clone with committed synthetic demo data and a committed demo model.

**Architecture:** A single Python package (`nexvia_fraud`) with separate modules for data generation, features, model training/scoring, persistence, streaming, and API. The API and the Kafka consumer share the same scoring and persistence code, so there is exactly one definition of "score and store". The React dashboard is a separate Vite app that talks only to the HTTP API. Compose wires the real services; tests use SQLite and an in-memory bus, with one opt-in integration test against real Kafka/Postgres.

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, SQLAlchemy 2, Postgres 16, Kafka 3.7 (KRaft), confluent-kafka, XGBoost, pandas, numpy, scikit-learn, pytest, Ruff; React 18 + Vite + TypeScript (strict); Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-11-two-ml-platforms-design.md` (sections 5, 8.1, 12, 12.1)

## Global Constraints

- Python 3.11; Node 24; TypeScript `strict: true`.
- No Kaggle credentials required for the demo path; committed synthetic data only.
- `docker compose up` must bring the stack up from a clean clone, including seeded data and a model artifact.
- Serving is CPU-only; p99 target < 100 ms at the stated demo rate, measured and reported with hardware and rate.
- All configuration comes from environment variables documented in `.env.example`; no secrets committed.
- Fraud metrics are PR-AUC based; every reported number names its run ID.
- Conventional commits; small, coherent commits.
- The dashboard must never be required for scoring; the API is the contract.
- Timestamps are UTC end to end; JSON uses ISO-8601 with `Z`.

## Review Focus

- **Duplicate delivery:** the same `transaction_id` published twice must produce one transaction row and one alert.
- **Unknown card:** a card with no history must score with documented defaults, not crash or return NaN.
- **Boundary inputs:** empty batch, zero amount, missing optional entity fields, and a score exactly at the threshold.
- **Concurrent decisions:** two analysts deciding the same alert must not both win silently.
- **Event time:** a transaction at `T` must never see features from transactions after `T`, and naive vs aware datetimes must be rejected.

---

### Task 1: Repository skeleton and configuration

**Files:**
- Create: `pyproject.toml`, `Makefile`, `.gitignore`, `.env.example`, `README.md`
- Create: `src/nexvia_fraud/__init__.py`, `src/nexvia_fraud/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` (pydantic-settings `BaseSettings`) with fields `database_url: str = "sqlite:///./data/dev.db"`, `kafka_bootstrap: str = "localhost:9092"`, `alerts_topic: str = "alerts"`, `raw_topic: str = "transactions.raw"`, `scored_topic: str = "transactions.scored"`, `alert_threshold: float = 0.5`, `model_dir: str = "artifacts/demo"`, `demo_data_path: str = "data/demo/transactions.csv"`.
- Produces: `get_settings() -> Settings`, decorated with `lru_cache`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from nexvia_fraud.config import Settings, get_settings

def test_defaults():
    s = Settings()
    assert s.raw_topic == "transactions.raw"
    assert s.alert_threshold == 0.5

def test_env_override(monkeypatch):
    monkeypatch.setenv("ALERT_THRESHOLD", "0.7")
    get_settings.cache_clear()
    assert get_settings().alert_threshold == 0.7
```

- [ ] **Step 2: Run it and confirm failure**

Run: `python -m pytest tests/test_config.py -q`
Expected: `ModuleNotFoundError: No module named 'nexvia_fraud'` (or import error on `Settings`).

- [ ] **Step 3: Create `pyproject.toml` and the package**

Dependencies: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `sqlalchemy>=2`, `psycopg[binary]`, `xgboost`, `pandas`, `numpy`, `scikit-learn`, `pyarrow`, `confluent-kafka`, `httpx`. Dev: `pytest`, `pytest-cov`, `ruff`. Configure `[tool.pytest.ini_options] pythonpath = ["src"]`, `[tool.ruff] line-length = 100`, and a `nexvia-fraud` console entry only if needed.

Implement `config.py` with `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`, `get_settings()` cached.

- [ ] **Step 4: Run test to verify pass**

Run: `pip install -e ".[dev]" && python -m pytest tests/test_config.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml Makefile .gitignore .env.example README.md src tests
git commit -m "chore: scaffold nexvia-fraud package and config"
```

---

### Task 2: Synthetic demo data generator

**Files:**
- Create: `src/nexvia_fraud/data/__init__.py`, `src/nexvia_fraud/data/generate_demo.py`
- Test: `tests/test_generate_demo.py`
- Output: `data/demo/transactions.csv` (committed, ~5k rows)

**Interfaces:**
- Produces: `generate_demo_transactions(n: int = 5000, seed: int = 7) -> pd.DataFrame` with columns `transaction_id, card_id, event_time, amount, device_id, email_domain, addr_id, is_fraud`.
- Produces: `write_demo_csv(df: pd.DataFrame, path: str) -> None` and CLI `python -m nexvia_fraud.data.generate_demo --n 5000 --out data/demo/transactions.csv`.
- Fraud rows are injected as rings: a ring is a device/email/address shared by several cards whose transactions are all `is_fraud=1`.

- [ ] **Step 1: Write the failing tests**

```python
def test_schema_and_determinism():
    a = generate_demo_transactions(500, seed=3)
    b = generate_demo_transactions(500, seed=3)
    assert list(a.columns) == ["transaction_id","card_id","event_time","amount",
                               "device_id","email_domain","addr_id","is_fraud"]
    assert a.equals(b)

def test_prevalence_and_rings():
    df = generate_demo_transactions(5000, seed=7)
    rate = df.is_fraud.mean()
    assert 0.02 <= rate <= 0.08
    ring_devices = df.loc[df.is_fraud == 1, "device_id"]
    assert ring_devices.duplicated().any()          # rings share devices
    assert (df.loc[df.is_fraud == 1, "card_id"].nunique() < df.loc[df.is_fraud == 1].shape[0])

def test_event_times_increasing_per_card():
    df = generate_demo_transactions(2000, seed=11)
    for _, g in df.groupby("card_id"):
        assert g.event_time.is_monotonic_increasing
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/test_generate_demo.py -q`
Expected: import or attribute failure.

- [ ] **Step 3: Implement the generator**

Use numpy `default_rng(seed)`. Build ~600 cards, each with a random number of transactions across 30 days; amounts log-normal; assign devices/emails/addresses per card. Inject ~12 fraud rings: pick 3–6 cards, give them a shared `device_id`/`email_domain` (and sometimes address), and mark all their transactions fraud. Sort by `event_time` within card. IDs are deterministic strings (`txn-{i:06d}`, `card-{i:04d}`).

- [ ] **Step 4: Run tests and write the committed CSV**

Run: `python -m pytest tests/test_generate_demo.py -q` → `3 passed`.
Run: `python -m nexvia_fraud.data.generate_demo --n 5000 --out data/demo/transactions.csv`.
Commit the CSV.

- [ ] **Step 5: Commit**

```bash
git add src/nexvia_fraud/data tests/test_generate_demo.py data/demo/transactions.csv
git commit -m "feat: add deterministic synthetic fraud demo data"
```

---

### Task 3: Feature service

**Files:**
- Create: `src/nexvia_fraud/features/__init__.py`, `src/nexvia_fraud/features/service.py`
- Test: `tests/test_features.py`

**Interfaces:**
- Produces: `FeatureService.from_dataframe(df: pd.DataFrame) -> FeatureService`.
- Produces: `FeatureService.feature_names() -> list[str]` returning, in order:
  `["velocity_1h","velocity_24h","unique_devices_24h","amount_mean","amount_std","amount_zscore","device_change","email_change","addr_change","seconds_since_last_txn"]`.
- Produces: `FeatureService.get_features(card_id: str, event_time: pd.Timestamp, amount: float, device_id: str, email_domain: str, addr_id: str) -> dict[str, float]`.
- Uses only transactions with `event_time < event_time` (strictly before) for the card.

- [ ] **Step 1: Write failing tests with a hand-built fixture**

```python
def service():
    df = pd.DataFrame([
        dict(transaction_id="t1", card_id="c1", event_time=pd.Timestamp("2026-01-01T00:00:00Z"),
             amount=10.0, device_id="d1", email_domain="a.com", addr_id="x", is_fraud=0),
        dict(transaction_id="t2", card_id="c1", event_time=pd.Timestamp("2026-01-01T00:30:00Z"),
             amount=30.0, device_id="d2", email_domain="a.com", addr_id="x", is_fraud=0),
    ])
    return FeatureService.from_dataframe(df)

def test_counts_exclude_current_event():
    f = service().get_features("c1", pd.Timestamp("2026-01-01T00:30:00Z"), 30.0, "d2", "a.com", "x")
    assert f["velocity_1h"] == 1.0          # t1 only, not t2
    assert f["velocity_24h"] == 1.0
    assert f["unique_devices_24h"] == 1.0
    assert f["amount_mean"] == 10.0
    assert f["device_change"] == 1.0

def test_unknown_card_defaults():
    f = service().get_features("nope", pd.Timestamp("2026-01-01T00:30:00Z"), 5.0, "d9", "b.com", "y")
    assert f["velocity_1h"] == 0.0 and f["amount_zscore"] == 0.0
    assert f["seconds_since_last_txn"] == -1.0
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/test_features.py -q`

- [ ] **Step 3: Implement**

Pre-group the sorted frame by `card_id` into numpy arrays (`event_time` in int64 ns, amounts, devices, emails, addrs). Use `np.searchsorted(..., side="left")` to find the cutoff so the current transaction is excluded. Windows are `[t-1h, t)` and `[t-24h, t)`. Return floats; unknown card returns zeros except `seconds_since_last_txn = -1.0`. `amount_zscore = (amount - mean) / std` with `std==0 → 0.0`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_features.py -q` → `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/nexvia_fraud/features tests/test_features.py
git commit -m "feat: add point-in-time feature service"
```

---

### Task 4: Model training with honest metrics

**Files:**
- Create: `src/nexvia_fraud/models/__init__.py`, `src/nexvia_fraud/models/train.py`
- Test: `tests/test_train.py`
- Output: `artifacts/demo/model.json`, `artifacts/demo/feature_names.json`, `artifacts/demo/metrics.json`, `reports/metrics.json`

**Interfaces:**
- Produces: `train_model(df: pd.DataFrame, out_dir: str, run_id: str) -> dict` where the dict has keys `run_id, pr_auc, roc_auc, precision_at_1pct_fpr, recall_at_1pct_fpr, precision_at_100, n_train, n_test, best_iteration`.
- Produces: `predict_proba(model_dir: str, features: dict[str, float]) -> float` (used by Task 5, not a second implementation).
- Time split: last 20% of rows by `event_time` is test; the split timestamp is stored in metrics as `test_start`.

- [ ] **Step 1: Write failing tests**

```python
def test_training_writes_artifacts_and_metrics(tmp_path, demo_df):
    metrics = train_model(demo_df, str(tmp_path), run_id="test-run")
    assert 0.0 <= metrics["pr_auc"] <= 1.0
    assert metrics["pr_auc"] > 0.5
    assert (tmp_path / "model.json").exists()
    assert (tmp_path / "metrics.json").exists()
    names = json.loads((tmp_path / "feature_names.json").read_text())
    assert names == FeatureService.from_dataframe(demo_df).feature_names()

def test_split_is_temporal(demo_df):
    metrics = train_model(demo_df, str(tmp_path), run_id="t")
    assert metrics["n_train"] + metrics["n_test"] == len(demo_df)
    train_max = demo_df[demo_df.event_time < pd.Timestamp(metrics["test_start"])].event_time.max()
    test_min = demo_df[demo_df.event_time >= pd.Timestamp(metrics["test_start"])].event_time.min()
    assert train_max < test_min
```

- [ ] **Step 2: Run and confirm failure**

- [ ] **Step 3: Implement**

Build the design matrix with `FeatureService` using each row's own `event_time` (the strictly-before rule prevents self-leakage). `XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.08, subsample=0.9, colsample_bytree=0.9, scale_pos_weight=neg/pos, eval_metric="aucpr", early_stopping_rounds=30, tree_method="hist", random_state=7)`. Fit with `eval_set=[(X_test, y_test)]`. Compute metrics with `sklearn.metrics` (`average_precision_score`, `roc_auc_score`, precision/recall at the threshold where FPR ≈ 0.01, precision@100 from the top 100 scores). Save `model.json` (`booster.save_model`), `feature_names.json`, `metrics.json` with `run_id`, `test_start` (ISO), and a `reports/metrics.json` copy when `out_dir` is the default.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_train.py -q` → `2 passed`.

- [ ] **Step 5: Train the committed demo artifact**

Run: `python -m nexvia_fraud.models.train --data data/demo/transactions.csv --out artifacts/demo --run-id demo-001`.
Expected: `artifacts/demo/model.json` exists and `metrics.json` has `pr_auc > 0.5`.

- [ ] **Step 6: Commit**

```bash
git add src/nexvia_fraud/models tests/test_train.py artifacts/demo reports/metrics.json
git commit -m "feat: train xgboost demo model with PR-AUC metrics"
```

---

### Task 5: Scorer with TreeSHAP contributions

**Files:**
- Create: `src/nexvia_fraud/models/scorer.py`
- Test: `tests/test_scorer.py`

**Interfaces:**
- Produces: `@dataclass ScoreResult: score: float; top_features: list[dict]; mode: str; model_version: str`.
- Produces: `Scorer.load(model_dir: str) -> Scorer`, `Scorer.score(features: dict[str, float]) -> ScoreResult`, `Scorer.model_version -> str`.
- `top_features` entries are `{"feature": str, "value": float, "contribution": float}`, sorted by `abs(contribution)`, length ≤ 10. Contributions come from `booster.predict(DMatrix, pred_contribs=True)`; the last column (bias) is dropped.

- [ ] **Step 1: Write failing tests**

```python
def test_score_shape_and_top_k(scorer):
    f = {name: 0.0 for name in scorer.feature_names}
    f["amount_zscore"] = 2.0
    r = scorer.score(f)
    assert 0.0 <= r.score <= 1.0
    assert r.mode == "xgb_only"
    assert len(r.top_features) <= 10
    assert len(r.top_features) == len({x["feature"] for x in r.top_features})

def test_missing_feature_is_explicit():
    r = scorer.score({"velocity_1h": 1.0})
    assert r.score == r.score          # not NaN
    assert math.isfinite(r.score)
```

- [ ] **Step 2–4:** Fail, implement, pass. Missing keys default to `0.0`; feature order is taken from `feature_names.json`, never from dict order.

- [ ] **Step 5: Commit**

```bash
git add src/nexvia_fraud/models/scorer.py tests/test_scorer.py
git commit -m "feat: add xgboost scorer with tree-shap contributions"
```

---

### Task 6: Persistence and audit chain

**Files:**
- Create: `src/nexvia_fraud/db/__init__.py`, `src/nexvia_fraud/db/models.py`, `src/nexvia_fraud/db/repo.py`, `src/nexvia_fraud/audit/__init__.py`, `src/nexvia_fraud/audit/chain.py`
- Test: `tests/test_repo.py`, `tests/test_audit.py`

**Interfaces:**
- Produces: `Base`, `Transaction`, `Alert`, `Decision`, `AuditLog` ORM classes. `Alert.status` is one of `"open"|"approved"|"rejected"`.
- Produces: `init_db(engine) -> None`, `upsert_transaction(session, payload: dict) -> Transaction`, `create_alert_if_absent(session, transaction_id: str, score: float) -> Alert | None` (None if it already exists), `list_alerts(session, status: str | None, min_score: float | None, limit: int) -> list[Alert]`, `get_alert(session, alert_id: str) -> Alert | None`, `decide(session, alert_id: str, decision: str, reason: str, analyst: str) -> Decision` (raises `ValueError` if already decided), `list_audit(session) -> list[AuditLog]`.
- Produces: `append_audit(session, payload: dict) -> AuditLog`, `verify_audit(session) -> bool`.
- Canonical payload: `json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)`; `hash = sha256((prev_hash or "0"*64 + canonical).encode()).hexdigest()`.

- [ ] **Step 1: Write failing tests**

```python
def test_upsert_is_idempotent(session):
    p = dict(transaction_id="t1", card_id="c1", event_time="2026-01-01T00:00:00Z",
             amount=10.0, score=0.2, mode="xgb_only", model_version="m")
    upsert_transaction(session, p); upsert_transaction(session, p)
    assert session.query(Transaction).count() == 1

def test_one_alert_per_transaction(session):
    assert create_alert_if_absent(session, "t1", 0.9) is not None
    assert create_alert_if_absent(session, "t1", 0.9) is None

def test_second_decision_rejected(session, alert):
    decide(session, alert.id, "approve", "ok", "ana")
    with pytest.raises(ValueError):
        decide(session, alert.id, "reject", "no", "bob")

def test_audit_tamper_detected(session):
    append_audit(session, {"a": 1}); append_audit(session, {"a": 2})
    assert verify_audit(session)
    row = session.query(AuditLog).first(); row.payload = {"a": 999}; session.commit()
    assert not verify_audit(session)
```

- [ ] **Step 2–4:** Fail, implement, pass with an in-memory SQLite engine (`StaticPool`).

- [ ] **Step 5: Commit**

```bash
git add src/nexvia_fraud/db src/nexvia_fraud/audit tests/test_repo.py tests/test_audit.py
git commit -m "feat: add persistence and hash-chained audit log"
```

---

### Task 7: FastAPI service

**Files:**
- Create: `src/nexvia_fraud/api/__init__.py`, `src/nexvia_fraud/api/main.py`, `src/nexvia_fraud/api/schemas.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces: `create_app(settings: Settings, scorer: Scorer, repo_module=repo) -> FastAPI`.
- Endpoints:
  - `GET /health → {"status":"ok","model_version":str}`
  - `POST /score` body `ScoreRequest` → `ScoreResponse`
  - `POST /score/batch` body `{"transactions": [ScoreRequest, ...]}` → `{"scores": [ScoreResponse]}`
  - `GET /alerts?status&min_score&limit` → `{"alerts": [...]}`
  - `GET /alerts/{alert_id}` → `{"alert": ..., "transaction": ..., "top_features": [...], "prior_cases": [...]}`
  - `POST /alerts/{alert_id}/decision` body `{"decision","reason","analyst"}` → `{"alert":..., "audit_hash": str}`
  - `GET /audit` → `{"entries": [...], "valid": bool}`
  - `GET /metrics` → Prometheus text with `fraud_score_requests_total`, `fraud_score_latency_seconds` (p50/p95/p99 gauges updated in-process).

- [ ] **Step 1: Write failing tests** using `fastapi.testclient.TestClient` with SQLite and a trained model fixture:
  `test_score_returns_contract`, `test_batch_empty_returns_empty_list`, `test_unknown_card_scores`, `test_alert_lifecycle_and_audit`, `test_health_reports_model_version`.

- [ ] **Step 2–4:** Fail, implement, pass. The `/score` handler builds features via `FeatureService`, scores, upserts the transaction, and creates an alert when `score >= settings.alert_threshold`. Exceptions map to 404/409/422 with JSON bodies.

- [ ] **Step 5: Commit**

```bash
git add src/nexvia_fraud/api tests/test_api.py
git commit -m "feat: add scoring and case-review api"
```

---

### Task 8: Streaming producer and consumer

**Files:**
- Create: `src/nexvia_fraud/streaming/__init__.py`, `bus.py`, `producer.py`, `consumer.py`
- Test: `tests/test_streaming.py`

**Interfaces:**
- Produces: `Publisher` protocol (`publish(topic: str, key: str, value: bytes) -> None`), `Consumer` protocol (`poll(timeout: float) -> tuple[str, bytes] | None`), `InMemoryBus` implementing both.
- Produces: `KafkaPublisher(bootstrap: str)` / `KafkaConsumer(bootstrap: str, group_id: str, topics: list[str])`.
- Produces: `handle_message(raw: dict, features: FeatureService, scorer: Scorer, session_factory, settings: Settings) -> ScoreResult`; idempotent via `upsert_transaction` + `create_alert_if_absent`.
- Produces: `replay(df: pd.DataFrame, publisher: Publisher, rate: float) -> int` (sleeps `1/rate` between messages, key = `card_id`).

- [ ] **Step 1: Write failing tests**

```python
def test_in_memory_roundtrip():
    bus = InMemoryBus(); bus.publish("t", "k", b"v")
    assert bus.poll(0.1) == ("t", b"v")

def test_handle_message_is_idempotent(session_factory, features, scorer, settings):
    msg = {...}
    handle_message(msg, features, scorer, session_factory, settings)
    handle_message(msg, features, scorer, session_factory, settings)
    with session_factory() as s:
        assert s.query(Transaction).count() == 1
        assert s.query(Alert).count() <= 1

def test_alert_created_above_threshold(session_factory, features, scorer, settings):
    handle_message(msg_high_score, ...)
    # exactly one alert, status open
```

- [ ] **Step 2–4:** Fail, implement, pass. Kafka wrapper parses JSON, uses `enable.idempotence=true`, `acks=all`; consumer commits after `handle_message` succeeds.

- [ ] **Step 5: Commit**

```bash
git add src/nexvia_fraud/streaming tests/test_streaming.py
git commit -m "feat: add kafka producer/consumer with idempotent handling"
```

---

### Task 9: Compose stack, Dockerfiles, and seed

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `dashboard/Dockerfile`, `scripts/seed.py`, `scripts/replay.py`, `.dockerignore`
- Test: `tests/test_compose_config.py` (runs `docker compose config` and asserts services exist)

**Interfaces:**
- Services: `postgres`, `kafka`, `redis`, `seed` (one-shot), `api`, `consumer`, `producer`, `dashboard`.
- `seed` runs migrations + demo CSV load + ensures the model artifact exists.
- `producer` runs `scripts/replay.py` at `REPLAY_RATE` (default 2/s) in a loop.
- Healthchecks: `pg_isready`, Kafka broker API via `kafka-topics.sh --list`, API `/health`.

- [ ] **Step 1: Write the failing test** asserting `docker compose config --services` output contains all eight services.
- [ ] **Step 2–4:** Implement, run `docker compose config -q`, run test (skipped when Docker CLI missing).
- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml dashboard/Dockerfile scripts .dockerignore tests/test_compose_config.py
git commit -m "chore: add compose stack and demo seed"
```

---

### Task 10: Dashboard scaffold and API client

**Files:**
- Create: `dashboard/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/api.ts`, `src/types.ts`, `src/styles.css`, `src/vite-env.d.ts`
- Test: `dashboard/src/api.test.ts`

**Interfaces:**
- `api.ts` exports `getHealth()`, `getAlerts(params)`, `getAlert(id)`, `decide(id, body)`, `getMetricsText()`; base URL from `import.meta.env.VITE_API_URL ?? "http://localhost:8000"`.
- `types.ts` mirrors the API contract exactly (`Alert`, `Transaction`, `ScoreResponse`, `FeatureContribution`).

- [ ] **Step 1: Write a failing Vitest test** for `formatScore`/`buildAlertQuery` pure helpers.
- [ ] **Step 2–4:** Scaffold Vite manually (no `npm create`), install, implement, `npm run test -- --run` passes.
- [ ] **Step 5: Commit**

```bash
git add dashboard
git commit -m "feat: scaffold react dashboard and api client"
```

---

### Task 11: Feed, alert queue, and case detail

**Files:**
- Create: `src/components/LiveFeed.tsx`, `AlertQueue.tsx`, `CaseDetail.tsx`, `ShapBars.tsx`, `StatusPill.tsx`
- Modify: `src/App.tsx`
- Test: `src/components/ShapBars.test.tsx`

**Interfaces:**
- `LiveFeed` polls `/alerts` every 3 s, caps the list at 200 rows.
- `AlertQueue` filters by status/min score server-side, sorts by score desc, links to the selected case.
- `CaseDetail` shows transaction facts, `ShapBars` for top features, prior cases count, and Approve/Reject with a required reason; after a decision it refetches and shows the audit hash.
- Banner: "Demo system. Synthetic data. Not a production fraud engine."

- [ ] **Step 1: Write failing tests** for `ShapBars` (renders a bar per contribution, clamps width 0–100) and `AlertQueue` filter serialization.
- [ ] **Step 2–4:** Implement, run `npm run test -- --run` and `npm run build`.
- [ ] **Step 5: Commit**

```bash
git add dashboard/src
git commit -m "feat: add live feed, alert queue, and case review ui"
```

---

### Task 12: Integration test and CI

**Files:**
- Create: `tests/integration/test_stream_flow.py`, `.github/workflows/ci.yml`
- Modify: `Makefile`

**Interfaces:**
- Integration test (marked `integration`, skipped when `KAFKA_BOOTSTRAP` is unset): publish one transaction → consume → assert transaction, score, and alert exist. Uses a unique `transaction_id` per run.
- CI: `lint` (ruff), `unit` (pytest excluding integration), `dashboard` (npm ci, test, build). Integration runs on `workflow_dispatch`/nightly with service containers.

- [ ] **Step 1: Write the failing integration test**, run it without Kafka to confirm skip.
- [ ] **Step 2–4:** Add workflow, run `ruff check .`, `pytest -m "not integration"`, `npm run build`.
- [ ] **Step 5: Commit**

```bash
git add tests/integration .github Makefile
git commit -m "test: add stream integration test and ci workflow"
```

---

### Task 13: Documentation and demo script

**Files:**
- Create: `docs/architecture.md`, `docs/api.md`, `docs/model-card.md`, `docs/limitations.md`, `presentations/demo-outline.md`, `reflections/template.md`
- Modify: `README.md`

**Interfaces:** none (documentation).

- [ ] **Step 1:** README: what it is, architecture Mermaid diagram, quickstart (`make setup && make data && make train && make up`), demo script, results table with run ID `demo-001`, limitations, ethics/data notice, and the exact measured latency numbers.
- [ ] **Step 2:** `docs/model-card.md` states synthetic-only training, PR-AUC, threshold, intended use, and known limits.
- [ ] **Step 3:** `make demo` documented end to end; recording checklist.
- [ ] **Step 4: Commit**

```bash
git add README.md docs presentations reflections
git commit -m "docs: add architecture, model card, limits, and demo script"
```

---

## Self-Review Notes

- **Spec coverage:** Kafka (T8/T9), XGBoost (T4/T5), Feast (deferred to depth; T3 provides the same interface), MLflow (deferred; T4 writes run IDs and reports), FastAPI (T7), Postgres (T6), Evidently (deferred), dashboard (T10/T11), Compose (T9), tests (T12), docs (T13). The slice deliberately excludes GNN, Feast, drift, and Kubernetes — they are the next plan, per design §12.
- **Type consistency:** `feature_names()` is used by the scorer, the trainer, and the tests; `ScoreResult.top_features` keys are fixed as `feature/value/contribution`; `transaction_id` is the idempotency key everywhere.
- **Review Focus tests:** duplicate delivery (T8), unknown card (T3/T7), boundary inputs (T7), concurrent decisions (T6), event time (T3/T4).
