# Nexvia — Two ML Platforms: Design

Date: 2026-11-11
Status: Draft for approval

> **Update 2026-11-13 — submission constraint supersedes the two-repo decision.**
> The evaluation allows a single GitHub URL and asks for subfolders per project.
> Both projects now live in one repository: `nexvia-fraud/` and `nexvia-imaging/`.
> §4 approach 3 (shared monorepo, rejected) and §7 are superseded on this point;
> the fraud history was imported with `git subtree`, and each folder keeps its own
> README, tests, and tooling.
Scope: `nexvia-fraud` and `nexvia-imaging`, two independent repositories, both submitted by 2026-12-15.

---

## 1. Intent and why

Two portfolio-grade AI/ML projects, each a complete system rather than a notebook:

1. **nexvia-fraud** — a real-time financial fraud detection platform: Kafka transaction stream, millisecond scoring, GNN-based fraud-ring linking, analyst dashboard with case workflow.
2. **nexvia-imaging** — an AI-assisted medical imaging platform: DICOM studies ingested by Orthanc, classified and segmented by PyTorch/MONAI models, Grad-CAM explanations, radiologist review with an audit log.

Why: the briefs reward a working demo, clean engineering, honest metrics, and documented limits. Two separate repos make each project independently cloneable and reviewable, and keep their stacks from contaminating each other.

## 2. Success criteria

A submission is done when, for each repo:

- `docker compose up` brings the full stack up from a clean clone, with seeded demo data.
- The documented demo path runs end to end without manual DB surgery.
- Training is reproducible from a Colab notebook and the resulting metrics/artifacts are committed under `reports/`.
- Tests pass in CI, including at least one integration test across the real service boundary (Kafka→API, Orthanc→worker).
- README has a Mermaid architecture diagram, setup, demo script, results table, limitations/bias section, and the required ethics notice.
- A 10-minute deck outline and per-intern reflection template exist.
- A screen recording of the working demo is linked.

## 3. Constraints

| Constraint | Consequence |
|---|---|
| Windows 11 dev machine, no NVIDIA GPU | All serving and demo runs CPU-only. Training moves to Colab. |
| Colab free tier (T4 16 GB, ~12 h sessions, preemptible) | Training must checkpoint and resume, fit in <2 h runs, and degrade to CPU with fewer epochs. |
| No Kaggle credentials on disk | Human partner supplies a Kaggle token; read from env/Colab secrets, never committed. Open mirrors (HuggingFace) remain the fallback. |
| No Minikube installed | Validate manifests on kind or Docker Desktop Kubernetes. Compose is the local demo path. |
| Hosting is Render (Python) + Vercel (React) | Services must be 12-factor, env-configured, and tolerate free-tier sleep, ephemeral disks, and managed Kafka/Redis/Postgres. |
| Two repos, one deadline | Shared conventions are copied, not shared as a package. No cross-repo imports. |
| Demo-scale only | Latency and throughput numbers are stated with hardware and message rate, never implied as production scale. |

## 3.1 What is actually required (from the two briefs)

**Fraud brief mandates:** Kafka, XGBoost, PyTorch Geometric GNN, Feast, MLflow, FastAPI, Kubernetes (Minikube acceptable), Evidently AI, an analyst dashboard, drift-triggered retraining, classification of heavy imbalance, and PR-AUC-based evaluation.

**Imaging brief mandates:** MONAI, PyTorch, Orthanc, Grad-CAM, DVC, Docker, React, a 3D U-Net segmentation model, an approve/reject review flow with audit log, and a prominent "education only, not clinical use" notice.

Both require: a working demo, a clean repo with README/setup, architecture diagram plus data/API docs, test results and metrics, a 10-minute deck, and individual reflections.

**Consequence:** the GNN and the 3D U-Net are hard requirements, not stretch goals. The XGBoost-only path is a resilience fallback, not a scope cut. Kubernetes is required for fraud only; imaging stops at Docker.

## 4. Approaches considered

1. **Sequential full-fidelity** — finish fraud completely, then imaging. Best depth, highest schedule risk.
2. **Demo-first vertical slices** — get one end-to-end thin path working per project, record it, then deepen. Lower risk of a half-built demo; requires deliberate refactoring.
3. **Shared monorepo core** — rejected: the brief and the user both require two standalone repos.

**Chosen: 2, applied twice.** For each repo: vertical slice → record → depth. Fraud goes first because it is CPU-friendly and its data is small.

## 5. Repository A — `nexvia-fraud`

### 5.1 Product behavior

A producer replays historical transactions into `transactions.raw` at a configurable rate. A consumer scores each one and writes to `transactions.scored`; scores above threshold create alerts. Analysts open the dashboard, inspect the transaction and its linked graph, mark fraud/not-fraud, and close the case. Every action is audited. Evidently monitors feature drift; a breached threshold creates a retraining request.

### 5.2 Stack and services

- **Kafka** (Bitnami KRaft, single broker) — topics `transactions.raw`, `transactions.scored`, `alerts`, `feedback`, `retraining.requests`.
- **Feast** — Redis online store, Parquet offline store, file-based registry. Feature views: `txn_velocity` (1h/24h counts, unique devices), `amount_profile` (user mean/std, amount z-score), `entity_change` (device/location/email change flags, time since last txn), `card_graph_stats` (degree, fraud-neighbour ratio).
- **XGBoost** — binary classifier, `scale_pos_weight`, early stopping on PR-AUC.
- **PyTorch Geometric** — heterogeneous graph (`card`, `device`, `email`, `addr`), GraphSAGE node classification, exported TorchScript.
- **Blender** — logistic stacker over XGBoost probability and GNN probability, fitted on out-of-fold predictions. Falls back to XGBoost-only if the GNN artifact is absent.
- **MLflow** — tracking server in Compose; runs also exported as JSON/PNG into `reports/`.
- **FastAPI** — `/score`, `/score/batch`, `/health`, `/metrics`; p99 target <100 ms at demo rate on the dev machine.
- **Postgres** — cases, decisions, audit log, retraining requests. **Redis** — Feast online store + score cache.
- **Evidently** — scheduled drift job (APScheduler container) writing HTML + JSON, plus a `drift_score` gauge.
- **React + Vite + TS** — live feed, alert queue, case detail, fraud-ring graph, model/drift page.
- **Kubernetes** — Kustomize manifests validated on kind; Compose is the demo path.

### 5.3 Data

IEEE-CIS Fraud Detection (transaction + identity tables). Chosen over PaySim because it carries device, email, and address fields, which the GNN requirement needs. PaySim remains a fallback loader.

Graph construction: card as account node; edges from shared device, email domain, address, and rapid successive transactions. Node labels from fraud rate of associated transactions. Train/validation split by time to avoid leakage.

### 5.4 Scoring path

1. Producer publishes raw transaction.
2. Consumer calls `get_online_features` for the card/device entities, then `POST /score` internally (or imports the scorer for in-process latency).
3. Scorer runs XGBoost + GNN blend, writes score and top SHAP contributions.
4. Threshold breach → alert row + Kafka `alerts`; dashboard polls or uses SSE.

### 5.5 Dashboard

- **Live feed** — recent transactions, score, decision, throughput.
- **Alert queue** — filter by score, status, amount; sortable.
- **Case detail** — transaction facts, SHAP waterfall, linked-entity graph (force layout), prior cases for the same entities, Approve/Reject + reason.
- **Model page** — PR curve, threshold table, current drift report, retraining requests.
- **Audit page** — hash-chained decision log, CSV export.

### 5.6 Metrics and tests

PR-AUC, ROC-AUC, precision/recall at 1% FPR, precision@100, confusion matrix at the chosen threshold. Latency p50/p95/p99 from k6/locust at a stated rate. Feast online/offline parity test. No-leakage test on time split. Graph-builder unit tests. Integration test: publish → consume → score → alert row. Playwright smoke test for the review flow.

## 6. Repository B — `nexvia-imaging`

### 6.1 Product behavior

A study pushed to Orthanc triggers a worker. The worker fetches the series via DICOMweb, runs the classifier (and the segmenter for CT), produces Grad-CAM overlays, writes a DICOM Structured Report and Secondary Capture back to Orthanc, and stores a JSON summary in Postgres. The radiologist opens the viewer, sees image + overlay + confidence, approves or rejects with a comment. Every decision is immutably logged.

### 6.2 Stack and services

- **Orthanc** with DICOMweb + PostgreSQL index; demo studies are generated as real DICOM.
- **Worker** — FastAPI + polling `/changes?type=stable-studies`; idempotent by `StudyInstanceUID` + `SOPInstanceUID`.
- **PyTorch** — DenseNet-121 multi-label classifier (14 NIH findings), transfer learning.
- **MONAI** — 3D U-Net for spleen segmentation on CT; sliding-window inference.
- **Grad-CAM** — `pytorch-grad-cam`, layer4 of DenseNet; overlay PNG per finding.
- **DVC** — dataset pointers, local remote, reproducible fetch scripts.
- **React + Cornerstone3D** — DICOMweb viewer, window/level, overlay toggle, segmentation layer.
- **Postgres** — studies, AI results, decisions, hash-chained audit log.
- **Docker Compose** — Orthanc, Postgres, worker, API, viewer. K8s manifests optional.

### 6.3 Data and DICOM path

- **Classification:** NIH ChestX-ray14 subset (frontal, 14 labels), streamed from a HuggingFace mirror into Colab. CheXpert is out of scope (registration + ~400 GB).
- **Segmentation:** MSD Task 09 Spleen (41 CT volumes), small enough for T4 training and meaningful Dice.
- **DICOM generation:** datasets are PNG/NIfTI, so `data/make_dicom.py` converts a curated demo set into valid CR and CT series with synthetic but structurally correct tags. This is the bridge that makes Orthanc and the viewer real. Clearly labeled synthetic in `PatientName`/`StudyDescription`.
- **DVC:** `data/` tracked, `dvc-storage/` as local remote, small fixtures committed so tests do not need the full set.

### 6.4 Inference path

1. Orthanc webhook/poller detects a new stable study.
2. Worker downloads via DICOMweb, builds a MONAI transform pipeline (resize 224, normalize, no train augmentation).
3. Classifier returns per-label probabilities; Grad-CAM for the top-k labels.
4. If modality is CT and the series matches the spleen protocol, run 3D U-Net and convert the mask to DICOM SEG.
5. Write SR + SC to Orthanc; upsert result JSON in Postgres.
6. Viewer loads images from Orthanc DICOMweb and results from the API.

### 6.5 Viewer and safety

Study list with status (pending / analyzed / reviewed), viewer with AI panel (findings ranked, confidence bars, heatmap toggle, segmentation toggle), Approve/Reject + comment, audit log. A persistent banner: **"For education and research only. Not a medical device. Do not use for clinical decisions."** Limits page covers dataset label noise, demographic bias from missing metadata, single-dataset evaluation, no external validation, and failure modes (poor-quality images, off-protocol series).

### 6.6 Metrics and tests

Per-label AUROC, mean AUROC, sensitivity/specificity at the deployed threshold, calibration plot, spleen Dice. Grad-CAM sanity checks (finite, in-bounds, non-degenerate). Integration test with a real Orthanc container uploading a fixture study. Playwright review flow. Audit-chain verification test.

## 7. Cross-repo conventions (copied, not shared)

- Python 3.11, `uv` or pip-tools lockfile, Ruff + Black, pytest, pre-commit.
- Node 24, Vite, TypeScript strict, Vitest, Playwright.
- `Makefile` targets: `setup`, `data`, `train`, `up`, `down`, `demo`, `test`, `lint`.
- `.env.example` with every variable documented; no secrets committed.
- `docs/architecture.md` (Mermaid), `docs/api.md`, `docs/model-card.md`, `docs/limitations.md`.
- `reports/` with metrics JSON, curves, run summaries.
- `presentations/` with a 10-minute deck outline and speaker notes.
- `reflections/` with one template per intern.
- GitHub Actions: lint + unit tests on PR. The container integration suite (Kafka/Orthanc service containers) runs on `workflow_dispatch` and nightly, not on every PR, to avoid flakiness and quota burn.
- Conventional commits, small history, README badges that reflect real status.

## 8. Training on Colab

Each repo has `notebooks/` (thin driver) and `training/` (importable code) so the same code runs locally on CPU and on Colab.

- Mount Drive for data/cache; set `KAGGLE_USERNAME`/`KAGGLE_KEY` from Colab secrets or upload the token.
- Write checkpoints every epoch to Drive; `resume_from` argument.
- MLflow tracking to a local file store inside the session; export `metrics.json`, params, and curve PNGs into the repo's `reports/`.
- Checkpoints are attached to GitHub Releases (all expected under 100 MB), not committed.
- Every notebook ends with a metrics table that is copied into the README; no metric is reported without the run ID.

## 8.1 Demo data, licensing, and clean-clone behavior

- **No Kaggle data is redistributed.** IEEE-CIS and NIH are fetched by `make data` using the user's credentials; MSD spleen is fetched under CC-BY-NC-SA with attribution and is not committed.
- A **synthetic demo dataset is committed**: fraud gets ~5k generated transactions with injected fraud rings; imaging gets six generated CR studies and one CT series with a synthetic spleen. `docker compose up` therefore works offline on a clean clone.
- **Demo weights are committed** under `artifacts/demo/` (XGBoost, GraphSAGE, DenseNet-121, 3D U-Net; total expected <100 MB). Full Colab-trained weights attach to GitHub Releases. Compose prefers Release weights when present and falls back to demo artifacts.
- `make data` upgrades the demo to real data; Colab training produces the reported production weights.
- Integration tests use only committed fixtures.

## 9. Deployment and demo

Target: **Vercel** hosts both React frontends; **Render** hosts the Python services. Local Compose remains the full-fidelity path; the Render/Vercel deployment is the public artifact.

**Fraud on Render**
- `api` — FastAPI Docker web service; Render Postgres, Upstash Redis (Feast online store), Upstash Kafka (SASL/TLS).
- `consumer`, `producer` — Render background workers replaying a bounded stream at a fixed low rate.
- `drift-monitor` — Render cron job running Evidently and writing the report summary to Postgres.
- Dashboard — Vercel static build pointing at the API URL.
- MLflow stays local with committed run exports; hosted serving does not depend on it.

**Imaging on Render**
- `orthanc` — Docker web service exposing DICOMweb; DICOM objects stored in Cloudflare R2 via Orthanc's S3 plugin and metadata in Render Postgres, so no persistent disk is required.
- `worker` — polls Orthanc and runs DenseNet + MONAI on CPU; seconds to a minute per study on free-tier CPU, acceptable for a demo.
- `api` — results, decisions, audit log, study list.
- Viewer — Vercel, Cornerstone3D against Orthanc DICOMweb.
- Six CR studies and one CT study are seeded into Orthanc by a script on first boot.

**Free-tier realities**
- Render free services sleep when idle; first request can take ~50 s. A cron ping keeps demos warm during review windows, and the README states this.
- Upstash Kafka/Redis and Render Postgres have size caps, so the hosted demo replays a bounded stream rather than the full dataset.
- No GPU on Render; training stays on Colab.
- Secrets live in Render/Vercel environment variables; `.env.example` documents every key; nothing sensitive is committed.

**Kubernetes:** Kustomize manifests for both repos, applied to kind or Docker Desktop Kubernetes, with `kubectl get pods` evidence in docs. Fraud must actually run there; imaging is validated to Compose parity.

**Recordings:** produced regardless of hosting, because free-tier sleeps and outages must not break submission. Scripted 5–8 minute walkthrough per repo, Playwright video where possible plus a narrated screen capture.


## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Colab preemption / T4 unavailable | Resumable checkpoints; runs segmented by epoch; CPU fallback config. |
| IEEE-CIS needs Kaggle auth | Env-based credentials; PaySim loader as fallback; document both. |
| NIH data too large for Colab disk | Stream a fixed subset, cache to Drive, keep an index file. |
| DICOM conversion is fiddly | Build `make_dicom.py` early; validate with Orthanc before model work. |
| GNN inference too slow on CPU | Precompute embeddings per card nightly; small GraphSAGE; blend falls back to XGBoost. |
| Latency target missed on CPU | State measured numbers honestly; optimize Feast caching and model size. |
| Scope creep | Vertical slice + recording first; depth features are additive and individually shippable. |

## 11. Decisions made by the builder (my calls)

- IEEE-CIS over PaySim; NIH subset + MSD spleen over CheXpert/Decathlon-full.
- React for both dashboards (spec allows Streamlit for fraud; React is the stronger artifact).
- Cornerstone3D for the imaging viewer.
- Kafka in KRaft mode, single broker; no Zookeeper.
- Postgres for cases/audit; Redis for Feast online + cache.
- MLflow file-store export under `reports/`; no external tracking service.
- kind or Docker Desktop Kubernetes for manifest validation; Compose for demos.
- Hash-chained audit logs in both repos to make "audit log" meaningful rather than a table.
- Auth is a seeded demo JWT with three roles; not a security product, documented as such.
- Hosting: Vercel frontends + Render services, Upstash Kafka/Redis, Render Postgres, Cloudflare R2 for DICOM objects.
- Both repos are public from day one.

## 12. Build order

1. Workspace conventions, repo skeletons, CI, docs templates.
2. **Fraud vertical slice:** producer → Kafka → FastAPI scorer (XGBoost only) → Postgres → dashboard review. Record.
3. **Fraud depth:** Feast, GNN + blend, SHAP, Evidently drift, retraining request, K8s, tests, metrics.
4. **Imaging vertical slice:** DICOM generator → Orthanc → worker → classifier + Grad-CAM → viewer review. Record.
5. **Imaging depth:** 3D U-Net, DICOM SR/SEG, audit chain, limits/bias, tests, metrics, K8s.
6. **Submission pass:** READMEs, diagrams, API docs, model cards, decks, reflections, recordings, final verification.

## 12.1 Cut lines and gates

- **MVP (must ship):** every mandated stack item working on demo data; one recorded end-to-end demo per repo; tests, metrics, docs, deck outline, reflection templates.
- **Stretch (cut in this order):** DICOM SEG output (PNG overlay is the MVP), full-dataset Colab retraining, extra dashboard pages, Kubernetes for imaging.
- **Gates:** fraud demo recorded by Nov 21; imaging demo recorded by Dec 5; submission freeze Dec 12.

## 13. Open questions for the human partner

1. **People** — how many interns, and whose names/roles go into the reflections and deck? The templates ship with placeholders until answered.
2. **Accounts** — will you own the Render/Vercel/Upstash/R2 accounts and connect the repos, or should I prepare configs and you click deploy?
3. **Branding** — is "Nexvia" correct for both repos? Defaulting to `nexvia-fraud` and `nexvia-imaging`.

