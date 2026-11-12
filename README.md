# Nexvia — AI/ML Portfolio

Single submission repository containing both allotted projects. Each project lives in its own folder with its own README, tests, and deliverables.

| Folder | Project | Status |
|---|---|---|
| [`nexvia-fraud/`](nexvia-fraud/) | Real-time financial fraud detection: Kafka stream, XGBoost + GraphSAGE blend, analyst case review, drift monitoring | **Built** — end-to-end demo, 71 unit tests, Compose + K8s |
| [`nexvia-imaging/`](nexvia-imaging/) | AI-assisted medical imaging: DICOM/Orthanc, DenseNet + 3D U-Net, Grad-CAM, radiologist review | **Next** — scope defined, implementation not started |

> Both are education projects. The fraud system runs on synthetic data; the imaging system will use public research datasets with an explicit "not for clinical use" notice.

## Repository layout

```
.
├── nexvia-fraud/          # project 1 (complete vertical slice + depth)
│   ├── src/nexvia_fraud/  # API, streaming, features, models, drift, audit
│   ├── dashboard/         # React + Vite review UI
│   ├── tests/             # unit + integration
│   ├── artifacts/demo/    # trained XGBoost, GraphSAGE, blend, reference data
│   ├── docker-compose.yml
│   ├── k8s/               # Kustomize manifests
│   └── docs/              # architecture, API, model card, limitations
├── nexvia-imaging/        # project 2 (scaffold + scope)
├── docs/superpowers/      # design spec and implementation plans
├── .github/workflows/     # CI for the whole repository
└── README.md
```

## Quickstart — fraud project

Requires Docker Desktop with Compose.

```bash
cd nexvia-fraud
docker compose up --build
```

- Dashboard: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>

Without Docker:

```bash
cd nexvia-fraud
python -m pip install -e ".[dev]"
python -m nexvia_fraud.data.generate_demo --n 5000 --out data/demo/transactions.csv
python -m nexvia_fraud.models.train --data data/demo/transactions.csv --out artifacts/demo --run-id demo-001
python -m nexvia_fraud.models.gnn --data data/demo/transactions.csv --out artifacts/demo --run-id demo-gnn-001
python scripts/seed.py --limit 600
uvicorn nexvia_fraud.api.app:app --port 8000
```

Full details, metrics, architecture diagrams, and limitations are in [`nexvia-fraud/README.md`](nexvia-fraud/README.md).

## What is demonstrated

- **Streaming correctness:** at-least-once Kafka delivery, idempotent writes, fail-fast consumer.
- **Point-in-time features:** strictly-before event semantics, tested for leakage.
- **Imbalance-aware ML:** PR-AUC, precision/recall at a fixed FPR, precision@100, calibration caveats.
- **Graph learning:** heterogeneous GraphSAGE with a pre-test-graph evaluation to avoid future edges.
- **Model operations:** Evidently drift reports, one-open-request retraining gate, hash-chained audit log.
- **Serving:** FastAPI with measured p50/p99, graceful XGBoost-only fallback.
- **Delivery:** Docker Compose, Kustomize manifests, GitHub Actions, committed demo artifacts.

## Tests

```bash
cd nexvia-fraud
python -m pytest -m "not integration" -q   # 71 unit tests
python -m pytest -m integration -q          # requires Docker services
cd dashboard && npm test && npm run build
```

CI runs the unit and dashboard suites on every push; the integration suite runs on `workflow_dispatch` and nightly.

## Documentation

- Design and decisions: [`docs/superpowers/specs/2026-11-11-two-ml-platforms-design.md`](docs/superpowers/specs/2026-11-11-two-ml-platforms-design.md)
- Implementation plans: [`docs/superpowers/plans/`](docs/superpowers/plans/)
- Fraud architecture: [`nexvia-fraud/docs/architecture.md`](nexvia-fraud/docs/architecture.md)
- Fraud API: [`nexvia-fraud/docs/api.md`](nexvia-fraud/docs/api.md)
- Model card: [`nexvia-fraud/docs/model-card.md`](nexvia-fraud/docs/model-card.md)
- Limitations: [`nexvia-fraud/docs/limitations.md`](nexvia-fraud/docs/limitations.md)
- Kubernetes: [`nexvia-fraud/docs/kubernetes.md`](nexvia-fraud/docs/kubernetes.md)

## Submission note

The original design proposed two standalone repositories. The evaluation allows a single GitHub URL and asks for subfolders per project, so the projects are consolidated here. The fraud project's full commit history was imported with `git subtree`, so its development history remains inspectable.

## Data and ethics

No Kaggle or medical data is redistributed. Demo fraud data is generated deterministically by `nexvia-fraud/src/nexvia_fraud/data/generate_demo.py`. The imaging project will use public research datasets under their licenses and will carry a prominent non-clinical-use notice.

## Repository conventions

- Python 3.11, Node 24, TypeScript strict.
- Conventional commits.
- No secrets committed; `.env.example` documents every variable.
- CI at the repository root; each project owns its tests.
