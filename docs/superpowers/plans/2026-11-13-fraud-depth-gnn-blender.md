# Fraud Depth — GraphSAGE and the Blender

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the mandated graph model (heterogeneous GraphSAGE over card/device/email/address) and a logistic blender over XGBoost and GNN probabilities, with a graceful XGBoost-only fallback.

**Architecture:** A graph builder turns the transaction table into a `HeteroData` object. GraphSAGE is trained on cards from the training window with a card-level split. Card scores and embeddings for all cards are exported to Parquet. A logistic meta-model is fit on validation-window predictions. `Scorer` loads the XGBoost booster, the GNN score table, and the blend weights, and returns `mode="blended"` when a card has a GNN score, otherwise `mode="xgb_only"`.

**Tech Stack:** PyTorch 2.14 (CPU), PyTorch Geometric 2.8, scikit-learn, pandas, XGBoost (existing).

**Spec:** `docs/superpowers/specs/2026-11-11-two-ml-platforms-design.md` §5.2 (PyG/GraphSAGE), §5.4 (blend), §5.5 (model page).

## Global Constraints

- CPU-only training and inference. The demo GNN must train in under two minutes.
- The GNN is inductive: cards unseen during training must still be embeddable.
- Serving falls back to XGBoost-only when the GNN artifact or the card score is missing; `mode` must say which path ran.
- No fraud-label aggregates in node features (would leak the target).
- SHAP explanations remain the XGBoost contributions; document that the blend does not change them.
- Seeds fixed; metrics recorded with a run ID.

## Review Focus

- **Cold-start cards:** a card absent from the GNN score table must not crash and must report `xgb_only`.
- **Missing artifacts:** a repo without GNN files must still serve.
- **Probability space:** blending happens in log-odds, and the output is a probability in [0, 1].
- **Leakage:** edges and labels used for training come from the training window only; test cards are unseen.
- **Determinism:** two runs with the same seed produce the same metrics.

---

### Task 1: Heterogeneous graph builder

**Files:**
- Create: `src/nexvia_fraud/models/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- `build_graph(df: pd.DataFrame) -> tuple[HeteroData, pd.DataFrame]` where the frame has one row per card: `card_id, is_fraud, n_txn, amount_mean, amount_std, n_devices, n_emails, n_addrs`.
- `node_types = ["card", "device", "email", "addr"]`.
- Relations: `("card","uses","device")`, `("device","used_by","card")`, and the same for email/address. Node features are standardized degree/count features; never fraud labels.

- [ ] **Step 1: Failing test** — build a 6-transaction fixture with two cards sharing a device; assert the card node count, the device node count, both directions of each relation, and that the card frame has the expected columns and labels.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Commit.**

---

### Task 2: GraphSAGE training and artifacts

**Files:**
- Create: `src/nexvia_fraud/models/gnn.py`
- Test: `tests/test_gnn.py`

**Interfaces:**
- `train_gnn(df: pd.DataFrame, out_dir: str, run_id: str, epochs: int = 60, seed: int = 7) -> dict`.
- Split: cards seen in `event_time < validation_start` (the same 70% cutoff as XGBoost) are split 70/15/15 into train/val/test by card, seeded. Labels are card-level `is_fraud` (any fraud transaction in the window).
- Model: two `SAGEConv` layers inside `HeteroConv`, hidden 32, ReLU, linear head on `card`; `BCEWithLogitsLoss` with `pos_weight`.
- Early stopping on validation PR-AUC; restore the best state.
- After training, run inference on a graph built from the **full** dataset and write:
  - `artifacts/demo/gnn_model.pt`
  - `artifacts/demo/gnn_card_scores.parquet` (`card_id`, `gnn_score`, `split`)
  - `artifacts/demo/gnn_metrics.json` (`run_id`, `pr_auc`, `roc_auc`, `n_train_cards`, `n_val_cards`, `n_test_cards`, `epochs_run`).
- `load_gnn_scores(out_dir) -> dict[str, float]` for the scorer.

- [ ] **Step 1: Failing test** — `train_gnn(demo_df, tmp_path, "g", epochs=5)` writes the three files; metrics are finite; `0 <= pr_auc <= 1`; score table covers every card in the data; all scores in [0,1].
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Commit.**

---

### Task 3: Blender

**Files:**
- Modify: `src/nexvia_fraud/models/gnn.py`
- Test: `tests/test_blend.py`

**Interfaces:**
- `fit_blender(xgb_prob: np.ndarray, gnn_prob: np.ndarray, y: np.ndarray) -> dict` returns `{"coef": [a, b], "intercept": c, "n": int}` fitted on logits with `LogisticRegression`.
- `apply_blender(blend: dict, xgb_prob: float, gnn_prob: float) -> float` returns `sigmoid(a*logit(xgb) + b*logit(gnn) + c)`, clamped to [1e-6, 1-1e-6] before the logit.
- `train_gnn` writes `blend.json` using validation-window transaction predictions:
  - XGBoost model from `artifacts/demo/model.json` scores validation transactions;
  - GNN card scores join by `card_id`;
  - fit the blender on rows where both exist.

- [ ] **Step 1: Failing tests** — symmetric perfect predictors give positive coefficients; `apply_blender` stays in [0,1] for extreme inputs; `blend.json` exists and has finite coefficients.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Commit.**

---

### Task 4: Scorer integration and fallback

**Files:**
- Modify: `src/nexvia_fraud/models/scorer.py`, `src/nexvia_fraud/scoring.py`
- Test: `tests/test_scorer.py`, `tests/test_streaming.py`

**Interfaces:**
- `Scorer.load(model_dir)` additionally loads `gnn_card_scores.parquet` and `blend.json` when present.
- `Scorer.score(features, card_id: str | None = None) -> ScoreResult`; `ScoreResult` gains `gnn_score: float | None = None`.
- `mode` is `"blended"` when a card score exists and the blender is loaded, else `"xgb_only"`.
- `score_transaction` passes `payload["card_id"]`.

- [ ] **Step 1: Failing tests** — a trained fixture directory plus a hand-written `gnn_card_scores.parquet`/`blend.json` yields `mode="blended"` and a finite `gnn_score` for a known card; an unknown card yields `mode="xgb_only"` and `gnn_score is None`; removing the GNN files still serves.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Commit.**

---

### Task 5: API and dashboard surface

**Files:**
- Modify: `src/nexvia_fraud/api/schemas.py`, `src/nexvia_fraud/api/main.py`, `dashboard/src/types.ts`, `dashboard/src/components/CaseDetail.tsx`, `dashboard/src/components/LiveFeed.tsx`
- Test: `tests/test_api.py`, `dashboard/src/format.test.ts`

**Interfaces:**
- `ScoreResponse` gains `gnn_score: float | None`; `AlertDetail.transaction` already includes `mode`.
- Case detail shows a mode chip (`blended` / `xgb only`) and the GNN score when present.
- Live feed score cell shows a small `B` marker for blended rows.

- [ ] **Step 1:** extend the API test to assert the response has a `gnn_score` key (null when no GNN artifact).
- [ ] **Step 2–4:** implement; `pytest` and `npm run build` pass.
- [ ] **Step 5: Commit.**

---

### Task 6: Train the demo artifact and document

**Files:** `artifacts/demo/*`, `README.md`, `docs/model-card.md`, `docs/architecture.md`, `docs/limitations.md`, `reports/`

- [ ] Run `python -m nexvia_fraud.models.gnn --data data/demo/transactions.csv --out artifacts/demo --run-id demo-gnn-001`.
- [ ] Record GNN and blended metrics against the XGBoost baseline in the model card.
- [ ] Document the fallback, the card split, the full-graph inference caveat, and that SHAP still explains only the XGBoost component.
- [ ] Add the GNN run to the README results table.
- [ ] Commit.

## Self-Review Notes

- Spec coverage: PyG + GraphSAGE (§5.2), logistic blender (§5.2), fallback, model page mode display.
- No Feast or K8s here; those remain separate depth items.
- Review Focus has an owning test in Tasks 2–4.
