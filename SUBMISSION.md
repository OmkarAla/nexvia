# Submission - Nexvia AI/ML Portfolio

**Repository:** <https://github.com/OmkarAla/nexvia>
**Branch:** `main`

One public repository containing both allotted projects:

| Folder | Brief | Course project | Project |
|---|---|---|---|
| [`AIML-01/`](AIML-01/) | AIML-01 | Project 2 | Nexvia Fraud - real-time fraud detection |
| [`AIML-02/`](AIML-02/) | AIML-02 | Project 1 | Nexvia Imaging - AI-assisted medical imaging |

## Start here

- Fraud: [`AIML-01/README.md`](AIML-01/README.md) - `cd AIML-01 && docker compose up --build`
- Imaging: [`AIML-02/README.md`](AIML-02/README.md) - `cd AIML-02 && docker compose up --build`
- Screenshots: [`AIML-01/docs/screenshots`](AIML-01/docs/screenshots) Â· [`AIML-02/docs/screenshots`](AIML-02/docs/screenshots)
- Design and plans: [`docs/superpowers/`](docs/superpowers/)
- Dataset setup: [`docs/data-setup.md`](docs/data-setup.md)

## Requirement matrix

### Fraud brief

| Requirement | Where | Evidence |
|---|---|---|
| Kafka streaming | `AIML-01/src/nexvia_fraud/streaming`, Compose `kafka` | producer/consumer tests, integration test |
| XGBoost | `models/train.py`, `models/train_ieee.py` | demo PR-AUC 0.740; IEEE-CIS sample PR-AUC 0.455 |
| PyTorch Geometric GNN | `models/graph.py`, `models/gnn.py` | GraphSAGE, card PR-AUC 0.582 |
| Feast | `AIML-01/feature_repo`, `features/feast_service.py` | training via historical retrieval + **serving via online lookup**, transaction-keyed, parity tests |
| MLflow | `src/nexvia_fraud/tracking.py`, Compose `mlflow` | params/metrics/artifacts logged per run |
| FastAPI | `src/nexvia_fraud/api` | `/score`, `/alerts`, `/drift`, `/audit` |
| Kubernetes | `AIML-01/k8s` | deployed on kind 2026-11-21; `docs/kubernetes-evidence.md` + `docs/screenshots/k8s-dashboard.png` |
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
| 3D U-Net segmentation | `training/train_unet.py`, `models/segmenter.py` | Dice 0.922 on MSD validation; worker writes a mask when one is found |
| Audit + approve/reject | `api/main.py`, `audit/chain.py` | hash chain, second decision 409 |
| Education notice | every UI page + docs | persistent banner and model card |

### Common deliverables

| Item | State |
|---|---|
| Working demo | Both apps run offline; fraud also deployed on kind |
| README + architecture + API + model card + limitations | Both projects |
| Tests | 81 backend (fraud), 38 backend (imaging), 12 + 2 frontend |
| Screenshots | Both projects |
| 10-minute deck | `presentations/AIML-01.pptx`, `presentations/AIML-02.pptx` |
| Individual reflections | `AIML-01/reflections/omkar-ala.md`, `AIML-02/reflections/omkar-ala.md` |
| Screen recording | **Pending** - script in each demo outline |
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

- **Screen recordings** are the only submission artifact still pending; scripts are at `AIML-01-demo-script.md` and `AIML-02-demo-script.md`.
- The real IEEE-CIS model uses a 30,000-row sample of 590,540 for runtime reasons; the EDA covers the full set.
- Feast serving is transaction-keyed, exact for replay; a streaming writer for card state is the production next step.
- The 3D U-Net is MSD-only (Dice 0.922); the synthetic demo phantom is out of distribution, so empty masks are suppressed.
- Cornerstone3D falls back to a server-rendered slice in this environment.
