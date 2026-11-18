# Submission — Nexvia AI/ML Portfolio

**Repository:** <https://github.com/OmkarAla/nexvia>
**Branch:** `main`

One public repository containing both allotted projects:

| Folder | Brief | Course project | Project |
|---|---|---|---|
| [`AIML-01/`](AIML-01/) | AIML-01 | Project 2 | Nexvia Fraud — real-time fraud detection |
| [`AIML-02/`](AIML-02/) | AIML-02 | Project 1 | Nexvia Imaging — AI-assisted medical imaging |

## Start here

- Fraud: [`AIML-01/README.md`](AIML-01/README.md) — `cd AIML-01 && docker compose up --build`
- Imaging: [`AIML-02/README.md`](AIML-02/README.md) — `cd AIML-02 && docker compose up --build`
- Screenshots: [`AIML-01/docs/screenshots`](AIML-01/docs/screenshots) · [`AIML-02/docs/screenshots`](AIML-02/docs/screenshots)
- Design and plans: [`docs/superpowers/`](docs/superpowers/)
- Dataset setup: [`docs/data-setup.md`](docs/data-setup.md)

## Requirement matrix

### Fraud brief

| Requirement | Where | Evidence |
|---|---|---|
| Kafka streaming | `AIML-01/src/nexvia_fraud/streaming`, Compose `kafka` | producer/consumer tests, integration test |
| XGBoost | `models/train.py`, `models/scorer.py` | PR-AUC 0.740, run `demo-001` |
| PyTorch Geometric GNN | `models/graph.py`, `models/gnn.py` | GraphSAGE, card PR-AUC 0.582 |
| Feast | `AIML-01/feature_repo`, `scripts/build_feast_features.py` | PIT retrieval + parity test; online materialization |
| MLflow | `src/nexvia_fraud/tracking.py`, Compose `mlflow` | params/metrics/artifacts logged per run |
| FastAPI | `src/nexvia_fraud/api` | `/score`, `/alerts`, `/drift`, `/audit` |
| Kubernetes | `AIML-01/k8s` | `kubectl kustomize` test, 8 Deployments + Job |
| Evidently AI | `src/nexvia_fraud/drift` | drift reports + one-open-request gate |
| Analyst dashboard | `AIML-01/dashboard` | live feed, case queue, SHAP, model health |
| Drift-triggered retraining | drift job + `/retraining-requests` | human-gated request, no auto-promote |
| Imbalance + PR-AUC | trainer + model card | PR-AUC, precision/recall @1% FPR, precision@100 |

### Imaging brief

| Requirement | Where | Evidence |
|---|---|---|
| MONAI | `AIML-02/training/train_unet.py` | 3D U-Net, sliding-window Dice, Colab notebook |
| PyTorch | `models/classifier.py` | DenseNet-121, 14 findings |
| Orthanc | Compose `orthanc`, `dicom/client.py` | DICOMweb + uploader, offline fallback |
| Grad-CAM | `models/classifier.py` | top-2 overlays, sanity test |
| DVC | `AIML-02/dvc.yaml`, `params.yaml` | `dvc repro` stage + lock |
| Docker | `AIML-02/docker-compose.yml` | Orthanc, Postgres, API, worker, dashboard |
| React | `AIML-02/dashboard` | Cornerstone3D path + rendered fallback |
| 3D U-Net segmentation | `training/train_unet.py` + notebook | training code; serving needs a trained checkpoint |
| Audit + approve/reject | `api/main.py`, `audit/chain.py` | hash chain, second decision 409 |
| Education notice | every UI page + docs | persistent banner and model card |

### Common deliverables

| Item | State |
|---|---|
| Working demo | Both apps run offline; Compose configs validated |
| README + architecture + API + model card + limitations | Both projects |
| Tests | 75 backend (fraud), 32 backend (imaging), 12 + 2 frontend |
| Screenshots | Both projects |
| 10-minute deck outline | Both projects |
| Reflection templates | Both projects |
| Screen recording | **Pending** — script in each demo outline |
| Public repo + commit history | This repository |

## Metrics

Fraud (`demo-001`, test window):

| Scores | PR-AUC | ROC-AUC |
|---|---|---|
| XGBoost | 0.740 | 0.877 |
| GNN | 0.805 | 0.894 |
| Blended | 0.839 | 0.893 |

Imaging (`colab-nih-sample-001`, NIH sample test split): mean AUROC **0.775** over 593 rows, patient-level split.

## Known gaps

- Feast is wired for offline definitions, PIT retrieval, and materialization; serving still uses the in-process `FeatureService` with a parity test. A streaming feature writer is needed before serving reads Feast online without replay leakage.
- The 3D U-Net has training code, a Colab notebook, and a smoke test, but no committed trained checkpoint or worker segmentation path yet.
- Cornerstone3D is the viewer path; its codec bundle failed at runtime in this environment, so the viewer falls back to a server-rendered slice. The fallback is visible in the screenshots.
- Docker was unavailable on the development machine during the final pass; Compose files are validated with `docker compose config` and the offline demo paths were used for screenshots.
- Screen recordings and the final deck (beyond outlines) are not yet produced.
