# nexvia-fraud

Real-time transaction fraud scoring with a Kafka stream, an XGBoost scorer, and an analyst review dashboard.

**Status:** vertical slice in progress. Everything here runs on synthetic demo data; no Kaggle credentials are required.

> Education project. Not a production fraud system. Scores are illustrative.

## Quickstart

```bash
make setup
make data
make train
make up
```

Then open the dashboard at http://localhost:5173 and the API docs at http://localhost:8000/docs.

See `docs/architecture.md` for the design, `docs/model-card.md` for metrics, and `docs/limitations.md` for what this does not do.
